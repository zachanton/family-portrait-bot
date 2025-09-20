# aiogram_bot_template/services/photo_processing.py
import cv2
import io
import mediapipe as mp
import numpy as np
import structlog
from typing import Optional, Tuple, Dict, List
from PIL import Image, ImageOps

logger = structlog.get_logger(__name__)

# --- MediaPipe setup ---
mp_face_mesh = mp.solutions.face_mesh
mp_selfie_segmentation = mp.solutions.selfie_segmentation

# FaceMesh landmark indices
FOREHEAD_TOP, CHIN_BOTTOM = 10, 152
LEFT_EYE_OUTER, RIGHT_EYE_OUTER = 263, 33
LEFT_FACE_OUTER, RIGHT_FACE_OUTER = 234, 454

FACE_OVAL_LANDMARK_INDICES = [
    10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288, 397, 365, 379, 378, 400, 377, 152, 148,
    176, 149, 150, 136, 172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109
]

# --- Pipeline parameters ---
TARGET_FACE_METRIC_PX = 220.0
MIN_SCALE, MAX_SCALE = 0.60, 1.80
SEGMENTATION_THRESHOLD = 0.10
OVERLAP_RATIO = 0.30  # used for edge sampling & legacy blending
HEAD_MARGIN_RATIO_OF_HEADH = 0.12
HEAD_MARGIN_PX_MIN = 18
HEAD_STRIP_TOP_EXTRA = 0.25
HEAD_STRIP_BOTTOM_EXTRA = 0.10
SEAM_SOFTEN_PX = 26
SEAM_SOFTEN_SIGMA = 6.0
CROP_ASPECT = 0.75  # internal person crop aspect for main composite

# --- Face crop parameters (for faces-only outputs) ---
# Keep background, enforce 9:16, crop larger to include hair.
FACE_CROP_ASPECT = 9.0 / 16.0  # width / height
FACE_MARGIN_LEFT_RIGHT_RATIO = 0.30
FACE_MARGIN_TOP_RATIO = 0.55
FACE_MARGIN_BOTTOM_RATIO = 0.30
FACE_EXTRA_HEIGHT_BIAS_TO_TOP = 0.65

# --- 3-people layout tuning ---
CENTER_MIDDLE_SCALE_3 = 0.80              # child 20% smaller
CENTER_CROP_EXTRA_UP_RATIO = 0.35         # additional top headroom for child crop (of head_h)

# --- Spacing between people in main composite ---
PERSON_GAP_RATIO = 0.06  # 6% of crop_w as visible gutter between people

# --- Output constraints (TikTok-ready main composite) ---
TIKTOK_CANVAS_W = 702
TIKTOK_CANVAS_H = 1280
DYNAMIC_BG_FILL = False
TIKTOK_BG_FALLBACK_BGR = (0, 0, 0)  # neutral dark gray in BGR

# --- I/O ---

def load_image_bgr_from_bytes(data: bytes) -> Optional[np.ndarray]:
    """Loads an image from bytes into a BGR NumPy array."""
    try:
        img = Image.open(io.BytesIO(data))
        img = ImageOps.exif_transpose(img)
        if img.mode != 'RGB':
            img = img.convert('RGB')
        return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    except Exception:
        logger.exception("Failed to load image from bytes.")
        return None

def convert_bgr_to_jpeg_bytes(img_bgr: np.ndarray, quality: int = 95) -> bytes:
    """Converts a BGR NumPy array to JPEG bytes."""
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    buf = io.BytesIO()
    Image.fromarray(img_rgb).save(buf, format="JPEG", quality=quality, optimize=True)
    return buf.getvalue()

def paste_transparent(background: np.ndarray, foreground: np.ndarray, x: int, y: int) -> np.ndarray:
    """Alpha-composites an RGBA foreground over a BGR background at (x, y)."""
    h, w = foreground.shape[:2]
    y_end, x_end = min(y + h, background.shape[0]), min(x + w, background.shape[1])
    h, w = y_end - y, x_end - x
    if w <= 0 or h <= 0:
        return background
    fg = foreground[:h, :w]
    alpha = fg[:, :, 3].astype(np.float32) / 255.0
    alpha_3 = np.dstack((alpha, alpha, alpha))
    bg_slice = background[y:y_end, x:x_end].astype(np.float32)
    blend = bg_slice * (1.0 - alpha_3) + fg[:, :, :3].astype(np.float32) * alpha_3
    background[y:y_end, x:x_end] = np.clip(blend, 0, 255).astype(np.uint8)
    return background

# --- Analysis & Helpers ---

def clamp(v, lo, hi):
    """Clamps a value v to the range [lo, hi]."""
    return max(lo, min(v, hi))

def analyze_and_segment_person(img_bgr: np.ndarray) -> Dict:
    """Returns image, face landmarks, and person segmentation mask."""
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    with mp_face_mesh.FaceMesh(static_image_mode=True, max_num_faces=1, refine_landmarks=False, min_detection_confidence=0.5) as fm:
        res = fm.process(img_rgb)
        if not res.multi_face_landmarks:
            raise ValueError("Face not found in image.")
        face_lm = res.multi_face_landmarks[0]
    with mp_selfie_segmentation.SelfieSegmentation(model_selection=0) as seg:
        seg_mask = seg.process(img_rgb).segmentation_mask
    return {"image_bgr": img_bgr, "face_landmarks": face_lm, "segmentation_mask": seg_mask}

def _lm_to_px(face_lm, w: int, h: int) -> np.ndarray:
    """Converts MediaPipe landmarks to pixel coordinates."""
    return np.array([(p.x * w, p.y * h) for p in face_lm.landmark], dtype=np.float32)

def face_scale_metric(person_data: Dict) -> Optional[float]:
    """Calculates a consistent face size metric for normalization."""
    img = person_data["image_bgr"]; h, w = img.shape[:2]
    lm = _lm_to_px(person_data["face_landmarks"], w, h)
    iod = float(np.linalg.norm(lm[LEFT_EYE_OUTER] - lm[RIGHT_EYE_OUTER]))
    hh = float(np.linalg.norm(lm[FOREHEAD_TOP] - lm[CHIN_BOTTOM]))
    if not iod or not hh or iod <= 0 or hh <= 0:
        return None
    return float(np.sqrt(iod * hh))

def _rotate_build_rgba_and_stats(person_data: Dict) -> Dict:
    """Rotates, segments, and extracts key metrics for a single person."""
    img_bgr, mask, h, w = person_data["image_bgr"], person_data["segmentation_mask"], *person_data["image_bgr"].shape[:2]
    condition = np.stack((mask,) * 3, axis=-1) > SEGMENTATION_THRESHOLD
    person_bgr = np.where(condition, img_bgr, 0)
    alpha_channel = (np.clip(mask, 0.0, 1.0) * 255).astype(np.uint8)
    person_rgba = cv2.merge([*cv2.split(person_bgr), alpha_channel])

    lm_px = _lm_to_px(person_data["face_landmarks"], w, h)
    p_le, p_re = lm_px[LEFT_EYE_OUTER], lm_px[RIGHT_EYE_OUTER]
    angle_deg = float(np.degrees(np.arctan2(p_le[1] - p_re[1], p_le[0] - p_re[0])))
    center_eyes = (p_le + p_re) / 2.0
    M = cv2.getRotationMatrix2D((float(center_eyes[0]), float(center_eyes[1])), angle_deg, 1.0)

    rot_bgr = cv2.warpAffine(img_bgr, M, (w, h), flags=cv2.INTER_LINEAR, borderValue=(0, 0, 0))
    rot_rgba = cv2.warpAffine(person_rgba, M, (w, h), flags=cv2.INTER_LINEAR, borderValue=(0, 0, 0, 0))

    eyes_rot = M @ np.array([center_eyes[0], center_eyes[1], 1.0], dtype=np.float32)
    lm_hom = np.hstack([lm_px, np.ones((lm_px.shape[0], 1))])
    rotated_landmarks = (M @ lm_hom.T).T

    a = rot_rgba[:, :, 3]
    ys, xs = np.where(a > 10)
    top_y, bot_y = (int(ys.min()), int(ys.max())) if len(ys) > 0 else (0, h - 1)

    return {
        "rot_bgr": rot_bgr,
        "rot_rgba": rot_rgba,
        "eyes_xy": (float(eyes_rot[0]), float(eyes_rot[1])),
        "head_h": float(np.linalg.norm(lm_px[FOREHEAD_TOP] - lm_px[CHIN_BOTTOM])),
        "clearances": {"up": float(eyes_rot[1] - top_y), "down": float(bot_y - eyes_rot[1])},
        "rot_landmarks": rotated_landmarks
    }

def _extract_face_rgba(data: Dict) -> np.ndarray:
    """
    Extracts a rectangular 9:16 RGBA face crop WITH background (no background removal).
    The crop is enlarged to include hair. Alpha is fully opaque (255).
    """
    img_bgr = data["rot_bgr"]
    landmarks = data["rot_landmarks"]

    oval_points = landmarks[FACE_OVAL_LANDMARK_INDICES].astype(np.int32)
    x, y, bw, bh = cv2.boundingRect(oval_points)

    left = int(round(x - bw * FACE_MARGIN_LEFT_RIGHT_RATIO))
    right = int(round(x + bw + bw * FACE_MARGIN_LEFT_RIGHT_RATIO))
    top = int(round(y - bh * FACE_MARGIN_TOP_RATIO))
    bottom = int(round(y + bh + bh * FACE_MARGIN_BOTTOM_RATIO))

    if right <= left: right = left + 1
    if bottom <= top: bottom = top + 1

    curr_w = right - left
    curr_h = bottom - top
    target_ratio = FACE_CROP_ASPECT  # w/h

    # Expand the smaller dimension only (never shrink) to fit 9:16
    if curr_w / max(1, curr_h) > target_ratio:
        new_h = int(np.ceil(curr_w / target_ratio))
        extra = new_h - curr_h
        extra_top = int(round(extra * FACE_EXTRA_HEIGHT_BIAS_TO_TOP))
        extra_bottom = extra - extra_top
        top -= extra_top
        bottom += extra_bottom
    else:
        new_w = int(np.ceil(curr_h * target_ratio))
        extra = new_w - curr_w
        extra_left = extra // 2
        extra_right = extra - extra_left
        left -= extra_left
        right += extra_right

    face_bgr, _, _ = _pad_crop_with_offsets(img_bgr, left, top, right, bottom)
    face_rgba = cv2.cvtColor(face_bgr, cv2.COLOR_BGR2BGRA)
    face_rgba[:, :, 3] = 255
    return face_rgba

def _convert_rgba_to_bgr_on_solid_bg(img_rgba: np.ndarray, bg_color=(128, 128, 128)) -> np.ndarray:
    """Pastes an RGBA image onto a solid background, returning a BGR image."""
    h, w = img_rgba.shape[:2]
    background = np.full((h, w, 3), bg_color, dtype=np.uint8)
    return paste_transparent(background, img_rgba, 0, 0)

# --- Background helpers (interpolated bands) ---

def _make_interpolated_band(left_bg: np.ndarray, right_bg: np.ndarray, band_w: int, sample_w: int) -> np.ndarray:
    """
    Build an H x band_w x 3 band by horizontally interpolating between the
    right edge of left_bg and the left edge of right_bg. sample_w controls
    how wide edge samples are averaged for each side.
    """
    h = left_bg.shape[0]
    if band_w <= 0:
        return np.zeros((h, 0, 3), dtype=np.uint8)
    o = max(1, int(sample_w))
    left_strip = left_bg[:, -o:].astype(np.float32)   # H x o x 3
    right_strip = right_bg[:, :o].astype(np.float32)  # H x o x 3
    left_col = np.mean(left_strip, axis=1)            # H x 3
    right_col = np.mean(right_strip, axis=1)          # H x 3

    t = np.linspace(0.0, 1.0, band_w, dtype=np.float32)[None, :, None]  # 1 x W x 1
    left_img = np.repeat(left_col[:, None, :], band_w, axis=1)          # H x W x 3
    right_img = np.repeat(right_col[:, None, :], band_w, axis=1)        # H x W x 3
    band = left_img * (1.0 - t) + right_img * t
    return np.clip(band, 0, 255).astype(np.uint8)

# --- Faces-only composites ---

def _create_faces_only_composite(p1_data: Dict, p2_data: Dict) -> np.ndarray:
    """Creates a side-by-side composite of two extracted face crops (parents) for child pipeline."""
    face1_rgba = _extract_face_rgba(p1_data)
    face2_rgba = _extract_face_rgba(p2_data)

    h1, w1 = face1_rgba.shape[:2]
    h2, w2 = face2_rgba.shape[:2]

    # Align roughly by centers with a margin
    y_offset = (h1 // 2) - (h2 // 2)
    margin = int(max(p1_data['head_h'], p2_data['head_h']) * 0.20)

    canvas_w = w1 + w2 + margin
    canvas_h = max(h1 + abs(y_offset) if y_offset < 0 else h1,
                   h2 + abs(y_offset) if y_offset > 0 else h2) + margin * 2

    canvas = np.full((int(canvas_h), int(canvas_w), 3), 128, dtype=np.uint8)

    paste_y1, paste_x1 = margin + max(0, -y_offset), 0
    paste_y2, paste_x2 = margin + max(0, y_offset), w1 + margin

    canvas = paste_transparent(canvas, face1_rgba, paste_x1, paste_y1)
    canvas = paste_transparent(canvas, face2_rgba, paste_x2, paste_y2)
    return canvas

def _create_three_faces_composite(p1_data: Dict, p2_data: Dict, p3_data: Dict) -> np.ndarray:
    """
    Creates a side-by-side composite of three extracted faces for family portraits:
    parents share the same height, child is 20% smaller, all bottom-aligned.
    """
    face1_rgba = _extract_face_rgba(p1_data)
    face2_rgba = _extract_face_rgba(p2_data)
    face3_rgba = _extract_face_rgba(p3_data)

    h1, w1 = face1_rgba.shape[:2]
    h2, w2 = face2_rgba.shape[:2]
    h3, w3 = face3_rgba.shape[:2]

    parent_base_h = max(h1, h3)

    # Resize parents to same height
    parents_resized: List[np.ndarray] = []
    for face, h in [(face1_rgba, h1), (face3_rgba, h3)]:
        if h != parent_base_h:
            scale = parent_base_h / float(h)
            new_w = int(round(face.shape[1] * scale))
            parents_resized.append(cv2.resize(face, (new_w, parent_base_h), interpolation=cv2.INTER_LANCZOS4))
        else:
            parents_resized.append(face)
    face1_r, face3_r = parents_resized

    # Child 80% of parent height
    child_target_h = int(round(parent_base_h * CENTER_MIDDLE_SCALE_3))
    scale_child = child_target_h / float(h2)
    child_target_w = int(round(w2 * scale_child))
    face2_r = cv2.resize(face2_rgba, (child_target_w, child_target_h),
                         interpolation=cv2.INTER_AREA if scale_child < 1.0 else cv2.INTER_CUBIC)

    widths = [face1_r.shape[1], face2_r.shape[1], face3_r.shape[1]]
    margin = int(parent_base_h * 0.10)
    canvas_w = sum(widths) + (margin * 2)
    canvas_h = parent_base_h

    canvas = np.full((canvas_h, canvas_w, 3), 128, dtype=np.uint8)

    x = 0
    canvas = paste_transparent(canvas, face1_r, x, 0)
    x += face1_r.shape[1] + margin
    y_child = canvas_h - face2_r.shape[0]
    canvas = paste_transparent(canvas, face2_r, x, y_child)
    x += face2_r.shape[1] + margin
    canvas = paste_transparent(canvas, face3_r, x, 0)
    return canvas

# --- Basic image ops ---

def _resize(img: np.ndarray, scale: float) -> np.ndarray:
    """Resizes an image using an appropriate interpolation method."""
    if abs(scale - 1.0) < 1e-3:
        return img
    interp = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_CUBIC
    h, w = img.shape[:2]
    return cv2.resize(img, (int(round(w * scale)), int(round(h * scale))), interpolation=interp)

def _pad_crop_with_offsets(img: np.ndarray, x1: int, y1: int, x2: int, y2: int) -> Tuple[np.ndarray, int, int]:
    """Crops an image, adding padding if the crop region extends beyond the image bounds."""
    h, w = img.shape[:2]
    pad_left, pad_top = max(0, -x1), max(0, -y1)
    pad_right, pad_bottom = max(0, x2 - w), max(0, y2 - h)
    if any(p > 0 for p in (pad_left, pad_top, pad_right, pad_bottom)):
        img = cv2.copyMakeBorder(img, pad_top, pad_bottom, pad_left, pad_right, cv2.BORDER_REPLICATE)
        x1 += pad_left
        y1 += pad_top
    return img[y1:y2, x1:x2], pad_left, pad_top

def _soften_vertical_band(img_bgr: np.ndarray, cx: int, width: int, sigma: float) -> None:
    """Applies a vertical Gaussian blur to a specific band of the image to hide seams."""
    if width <= 0:
        return
    h, w = img_bgr.shape[:2]
    x0 = max(0, int(cx - width // 2))
    x1 = min(w, int(cx + (width + 1) // 2))
    if x1 <= x0:
        return
    roi = img_bgr[:, x0:x1]
    blurred = cv2.GaussianBlur(roi, ksize=(0, 0), sigmaX=sigma, sigmaY=0)
    img_bgr[:, x0:x1] = blurred

# --- TikTok canvas helpers ---

def _estimate_uniform_bg_color_from_borders(img_bgr: np.ndarray, border_ratio: float = 0.06) -> Tuple[int, int, int]:
    """Estimate a solid background color from image borders."""
    h, w = img_bgr.shape[:2]
    if h == 0 or w == 0:
        return TIKTOK_BG_FALLBACK_BGR
    b = max(1, int(round(min(h, w) * border_ratio)))
    mask = np.zeros((h, w), dtype=bool)
    mask[:b, :] = True
    mask[-b:, :] = True
    mask[:, :b] = True
    mask[:, -b:] = True
    border_pixels = img_bgr[mask]
    if border_pixels.size == 0:
        return TIKTOK_BG_FALLBACK_BGR
    median_color = np.median(border_pixels, axis=0)
    return tuple(int(c) for c in np.clip(median_color, 0, 255))

def _fit_to_tiktok_canvas(img_bgr: np.ndarray,
                          target_w: int = TIKTOK_CANVAS_W,
                          target_h: int = TIKTOK_CANVAS_H,
                          bg_color: Optional[Tuple[int, int, int]] = None) -> np.ndarray:
    """
    Fits the given image into a fixed 9:16 TikTok canvas by letterboxing with a solid color.
    No cropping or distortion is applied.
    """
    h, w = img_bgr.shape[:2]
    if h == 0 or w == 0:
        fill = bg_color if bg_color is not None else TIKTOK_BG_FALLBACK_BGR
        return np.full((target_h, target_w, 3), fill, dtype=np.uint8)

    if bg_color is None:
        if DYNAMIC_BG_FILL:
            bg_color = _estimate_uniform_bg_color_from_borders(img_bgr)
        else:
            bg_color = TIKTOK_BG_FALLBACK_BGR

    scale = min(target_w / w, target_h / h)
    new_w = max(1, int(round(w * scale)))
    new_h = max(1, int(round(h * scale)))

    interp = cv2.INTER_CUBIC if scale > 1.0 else cv2.INTER_AREA
    resized = cv2.resize(img_bgr, (new_w, new_h), interpolation=interp)

    canvas = np.full((target_h, target_w, 3), bg_color, dtype=np.uint8)
    x = (target_w - new_w) // 2
    y = (target_h - new_h) // 2
    canvas[y:y+new_h, x:x+new_w] = resized
    return canvas

# --- Main Function ---

def create_composite_image(*p_bytes_list: bytes) -> Tuple[Optional[bytes], Optional[bytes], Optional[bytes], Optional[bytes]]:
    """
    Builds a composite image from two or three source photos.
    The order of people in the composite is the same as the order of bytes passed.

    Returns:
        - For 2 people: (composite_jpeg, faces_only_jpeg, person1_face_jpeg, person2_face_jpeg)
        - For 3 people: (composite_jpeg, three_faces_jpeg, None, None)
        Returns (None, None, None, None) on any failure.
    """
    if not (2 <= len(p_bytes_list) <= 3):
        logger.error("Unsupported number of images for composite", count=len(p_bytes_list))
        return None, None, None, None

    try:
        # --- 1. Preprocessing ---
        p_bgr_list = [load_image_bgr_from_bytes(b) for b in p_bytes_list]
        if any(img is None for img in p_bgr_list):
            return None, None, None, None

        person_data = [analyze_and_segment_person(bgr) for bgr in p_bgr_list]
        scales = [clamp(TARGET_FACE_METRIC_PX / (face_scale_metric(d) or TARGET_FACE_METRIC_PX), MIN_SCALE, MAX_SCALE) for d in person_data]
        scaled_bgrs = [_resize(bgr, scale) for bgr, scale in zip(p_bgr_list, scales)]
        scaled_data = [analyze_and_segment_person(bgr) for bgr in scaled_bgrs]
        processed_people = [_rotate_build_rgba_and_stats(d) for d in scaled_data]

        # --- 2. Universal Cropping ---
        num_people = len(processed_people)
        up_common = min(p["clearances"]["up"] for p in processed_people)
        down_common = min(p["clearances"]["down"] for p in processed_people)
        crop_h = int(round(up_common + down_common))
        crop_w = int(round(crop_h * CROP_ASPECT))

        cropped_bgs: List[np.ndarray] = []
        cropped_persons_rgba: List[np.ndarray] = []

        for i, p_data in enumerate(processed_people):
            ex, ey = p_data["eyes_xy"]
            x1 = int(round(ex - crop_w / 2))
            y1 = int(round(ey - up_common))

            # Child (middle) gets extra headroom so hair is never cut.
            if num_people == 3 and i == 1:
                child_up = p_data["clearances"]["up"]
                extra_allow = max(0, int(round(child_up - up_common)))
                extra_target = int(round(p_data["head_h"] * CENTER_CROP_EXTRA_UP_RATIO))
                y1 -= min(extra_allow, extra_target)

            x2, y2 = x1 + crop_w, y1 + crop_h

            bg_crop, _, _ = _pad_crop_with_offsets(p_data["rot_bgr"], x1, y1, x2, y2)
            person_rgba_crop, _, _ = _pad_crop_with_offsets(p_data["rot_rgba"], x1, y1, x2, y2)
            cropped_bgs.append(bg_crop)
            cropped_persons_rgba.append(person_rgba_crop)

        # --- 3. Main Composite Background (with spacing) ---
        overlap_px = int(crop_w * OVERLAP_RATIO)        # for edge sampling
        gap_px = int(round(crop_w * PERSON_GAP_RATIO))  # visible gap

        if num_people == 3:
            # Replace child's background by a synthetic interpolation band of equal width
            synthetic_mid = _make_interpolated_band(cropped_bgs[0], cropped_bgs[2],
                                                    cropped_bgs[1].shape[1], overlap_px)
            bgs_for_comp = [cropped_bgs[0], synthetic_mid, cropped_bgs[2]]
        else:
            bgs_for_comp = cropped_bgs

        final_w = sum(bg.shape[1] for bg in bgs_for_comp) + gap_px * (num_people - 1)
        composite_bg = np.zeros((crop_h, final_w, 3), dtype=np.uint8)

        current_x = 0
        for i, bg in enumerate(bgs_for_comp):
            w_i = bg.shape[1]
            composite_bg[:, current_x:current_x + w_i] = bg
            current_x += w_i
            if i < len(bgs_for_comp) - 1:
                # Insert an interpolated gap between this bg and the next bg
                next_bg = bgs_for_comp[i + 1]
                band = _make_interpolated_band(bg, next_bg, gap_px, overlap_px)
                composite_bg[:, current_x:current_x + gap_px] = band
                _soften_vertical_band(composite_bg,
                                      current_x + gap_px // 2,
                                      min(SEAM_SOFTEN_PX, max(1, gap_px // 2)),
                                      SEAM_SOFTEN_SIGMA)
                current_x += gap_px

        final_image = composite_bg.copy()

        # --- 4. Foreground Layering (respect the same slots & gaps) ---
        paste_positions: List[int] = []
        cursor = 0
        for i in range(num_people):
            paste_positions.append(cursor)
            cursor += cropped_bgs[i].shape[1]
            if i < num_people - 1:
                cursor += gap_px

        if num_people == 3:
            # Parents first
            final_image = paste_transparent(final_image, cropped_persons_rgba[0], paste_positions[0], 0)
            final_image = paste_transparent(final_image, cropped_persons_rgba[2], paste_positions[2], 0)

            # Child resized to 80% and bottom-aligned, centered within its slot
            center_rgba = cropped_persons_rgba[1]
            ch, cw = center_rgba.shape[:2]
            scale = CENTER_MIDDLE_SCALE_3
            new_w = max(1, int(round(cw * scale)))
            new_h = max(1, int(round(ch * scale)))
            interp = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_CUBIC
            center_resized = cv2.resize(center_rgba, (new_w, new_h), interpolation=interp)

            y_center = final_image.shape[0] - new_h  # bottoms fixed
            slot_x = paste_positions[1]
            slot_w = cropped_bgs[1].shape[1]
            x_center = slot_x + (slot_w - new_w) // 2
            final_image = paste_transparent(final_image, center_resized, x_center, y_center)
        else:
            # Two people: just paste in their slots
            final_image = paste_transparent(final_image, cropped_persons_rgba[0], paste_positions[0], 0)
            final_image = paste_transparent(final_image, cropped_persons_rgba[1], paste_positions[1], 0)

        # --- 5. Letterbox to TikTok canvas (first return value) ---
        final_image_tiktok = _fit_to_tiktok_canvas(final_image)
        composite_jpeg = convert_bgr_to_jpeg_bytes(final_image_tiktok)

        # --- 6. Additional outputs (faces-only crops) ---
        faces_only_jpeg: Optional[bytes] = None
        p1_face_jpeg: Optional[bytes] = None
        p2_face_jpeg: Optional[bytes] = None

        if num_people == 2:
            p1_data, p2_data = processed_people[0], processed_people[1]
            faces_only_bgr = _create_faces_only_composite(p1_data, p2_data)
            faces_only_jpeg = convert_bgr_to_jpeg_bytes(faces_only_bgr)

            p1_face_rgba = _extract_face_rgba(p1_data)
            p2_face_rgba = _extract_face_rgba(p2_data)
            p1_face_bgr = _convert_rgba_to_bgr_on_solid_bg(p1_face_rgba)
            p2_face_bgr = _convert_rgba_to_bgr_on_solid_bg(p2_face_rgba)
            p1_face_jpeg = convert_bgr_to_jpeg_bytes(p1_face_bgr)
            p2_face_jpeg = convert_bgr_to_jpeg_bytes(p2_face_bgr)

        elif num_people == 3:
            # Father, Child, Mother
            p1, p2, p3 = processed_people[0], processed_people[1], processed_people[2]
            three_faces_bgr = _create_three_faces_composite(p1, p2, p3)
            faces_only_jpeg = convert_bgr_to_jpeg_bytes(three_faces_bgr)

        return composite_jpeg, faces_only_jpeg, p1_face_jpeg, p2_face_jpeg

    except Exception:
        logger.exception("A critical error occurred in create_composite_image.")
        return None, None, None, None

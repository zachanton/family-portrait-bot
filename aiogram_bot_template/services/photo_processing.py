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

# Kept for compatibility (not used for horizontal blends anymore)
OVERLAP_RATIO = 0.30
SEAM_SOFTEN_PX = 26
SEAM_SOFTEN_SIGMA = 6.0

# Person crop around eyes (w/h = 0.75) for the main vertical composite
CROP_ASPECT = 0.75  # width / height

# --- Face crop parameters (for individual portraits) ---
FACE_CROP_ASPECT = 9.0 / 16.0  # width / height
FACE_MARGIN_LEFT_RIGHT_RATIO = 0.30
FACE_MARGIN_TOP_RATIO = 0.55
FACE_MARGIN_BOTTOM_RATIO = 0.30
FACE_EXTRA_HEIGHT_BIAS_TO_TOP = 0.65

# --- 3-people layout tuning ---
CENTER_MIDDLE_SCALE_3 = 0.80
CENTER_CROP_EXTRA_UP_RATIO = 0.35

# --- Spacing for vertical stacks ---
VERTICAL_GAP_RATIO = 0.02
VERTICAL_MARGIN_RATIO = 0.03

# --- Output constraints (TikTok-ready canvas) ---
TIKTOK_CANVAS_W = 702
TIKTOK_CANVAS_H = 1280
DYNAMIC_BG_FILL = False
TIKTOK_BG_FALLBACK_BGR = (0, 0, 0)  # BGR

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

    # IMPORTANT:
    # - rot_bgr: replicate edges to avoid black wedges after rotation
    # - rot_rgba: keep transparent border so alpha doesn't grow
    rot_bgr = cv2.warpAffine(
        img_bgr, M, (w, h),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REPLICATE
    )
    rot_rgba = cv2.warpAffine(
        person_rgba, M, (w, h),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0, 0, 0, 0)
    )

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

def _build_tiktok_canvas(bg_sample: Optional[np.ndarray] = None) -> Tuple[np.ndarray, int, int, int, int, int]:
    """
    Returns: (canvas, canvas_w, canvas_h, gap_px, margin_top, margin_bottom)
    """
    canvas_w, canvas_h = TIKTOK_CANVAS_W, TIKTOK_CANVAS_H
    if DYNAMIC_BG_FILL and bg_sample is not None:
        bg_color = _estimate_uniform_bg_color_from_borders(bg_sample)
    else:
        bg_color = TIKTOK_BG_FALLBACK_BGR
    gap_px = max(8, int(round(canvas_h * VERTICAL_GAP_RATIO)))
    margin_top = max(12, int(round(canvas_h * VERTICAL_MARGIN_RATIO)))
    margin_bottom = margin_top
    canvas = np.full((canvas_h, canvas_w, 3), bg_color, dtype=np.uint8)
    return canvas, canvas_w, canvas_h, gap_px, margin_top, margin_bottom

def _stack_crops_vertically_on_tiktok(cropped_bgs: List[np.ndarray],
                                      cropped_persons_rgba: List[np.ndarray]) -> np.ndarray:
    """
    Vertically stacks people into a TikTok canvas. Each person block is resized
    (keeping aspect) to fill as much width as possible. If the total height
    exceeds the canvas, a uniform downscale factor is applied to all.
    """
    assert len(cropped_bgs) == len(cropped_persons_rgba)
    num = len(cropped_bgs)
    if num == 0:
        return np.full((TIKTOK_CANVAS_H, TIKTOK_CANVAS_W, 3), TIKTOK_BG_FALLBACK_BGR, dtype=np.uint8)

    canvas, canvas_w, canvas_h, gap_px, margin_top, margin_bottom = _build_tiktok_canvas(cropped_bgs[0])

    widths = [bg.shape[1] for bg in cropped_bgs]
    heights = [bg.shape[0] for bg in cropped_bgs]
    scales_to_full_width = [canvas_w / max(1.0, w) for w in widths]
    h_at_full_width = [int(round(h * s)) for h, s in zip(heights, scales_to_full_width)]

    total_h_full = sum(h_at_full_width) + gap_px * (num - 1) + margin_top + margin_bottom

    if total_h_full <= canvas_h:
        target_widths = [canvas_w for _ in widths]
        target_heights = h_at_full_width
    else:
        available = canvas_h - (margin_top + margin_bottom) - gap_px * (num - 1)
        sum_blocks = sum(h_at_full_width)
        global_scale = max(0.05, available / max(1, sum_blocks))
        target_widths = [max(1, int(round(canvas_w * global_scale))) for _ in widths]
        target_heights = [max(1, int(round(h * global_scale))) for h in h_at_full_width]

    y = margin_top
    for bg, fg, tw, th in zip(cropped_bgs, cropped_persons_rgba, target_widths, target_heights):
        interp_bg = cv2.INTER_AREA if (tw < bg.shape[1] or th < bg.shape[0]) else cv2.INTER_CUBIC
        bg_resized = cv2.resize(bg, (tw, th), interpolation=interp_bg)
        fg_resized = cv2.resize(fg, (tw, th), interpolation=cv2.INTER_AREA if interp_bg == cv2.INTER_AREA else cv2.INTER_CUBIC)

        bg_rgba = cv2.cvtColor(bg_resized, cv2.COLOR_BGR2BGRA)
        bg_rgba[:, :, 3] = 255

        x = (TIKTOK_CANVAS_W - tw) // 2
        canvas = paste_transparent(canvas, bg_rgba, x, y)
        canvas = paste_transparent(canvas, fg_resized, x, y)

        y += th
        if y < TIKTOK_CANVAS_H:
            y += gap_px

    return canvas

# --- Face extraction & portrait helpers ---

def _extract_face_rgba(data: Dict) -> np.ndarray:
    """
    Extracts a rectangular 9:16-ish RGBA face crop WITH background (no background removal).
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

    if right <= left:
        right = left + 1
    if bottom <= top:
        bottom = top + 1

    curr_w = right - left
    curr_h = bottom - top
    target_ratio = FACE_CROP_ASPECT  # w/h

    # Expand the smaller dimension only (never shrink) to approach 9:16
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

def _fit_face_rgba_to_tiktok_bgr(face_rgba: np.ndarray) -> np.ndarray:
    """
    Fits an RGBA face crop onto a TikTok canvas WITHOUT changing aspect.
    Background outside the fitted crop is filled by reflection (no blur).
    Uses BORDER_REFLECT_101 to avoid a visible seam on the edge pixel.
    Returns BGR canvas of size (TIKTOK_CANVAS_H, TIKTOK_CANVAS_W, 3).
    """
    h, w = face_rgba.shape[:2]
    if h == 0 or w == 0:
        return np.full((TIKTOK_CANVAS_H, TIKTOK_CANVAS_W, 3), TIKTOK_BG_FALLBACK_BGR, dtype=np.uint8)

    # Keep aspect ratio (FIT)
    scale = min(TIKTOK_CANVAS_W / float(w), TIKTOK_CANVAS_H / float(h))
    new_w = max(1, int(round(w * scale)))
    new_h = max(1, int(round(h * scale)))
    interp = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_CUBIC
    fg_rgba = cv2.resize(face_rgba, (new_w, new_h), interpolation=interp)

    # Convert to BGR (alpha not needed for reflection padding)
    fg_bgr = cv2.cvtColor(fg_rgba, cv2.COLOR_BGRA2BGR)

    # Symmetric padding to exact TikTok size using reflection (no black bars)
    pad_left = (TIKTOK_CANVAS_W - new_w) // 2
    pad_right = TIKTOK_CANVAS_W - new_w - pad_left
    pad_top = (TIKTOK_CANVAS_H - new_h) // 2
    pad_bottom = TIKTOK_CANVAS_H - new_h - pad_top

    canvas_bgr = cv2.copyMakeBorder(
        fg_bgr,
        top=pad_top,
        bottom=pad_bottom,
        left=pad_left,
        right=pad_right,
        borderType=cv2.BORDER_REFLECT_101
    )
    return canvas_bgr

# --- Faces-only vertical composites ---

def _create_faces_only_composite(p1_data: Dict, p2_data: Dict) -> np.ndarray:
    """
    Vertically stacks two face crops on a TikTok-sized canvas (no aspect distortion).
    """
    face1 = _extract_face_rgba(p1_data)
    face2 = _extract_face_rgba(p2_data)

    canvas, canvas_w, canvas_h, gap_px, margin_top, margin_bottom = _build_tiktok_canvas(face1[:, :, :3])

    widths = [face1.shape[1], face2.shape[1]]
    heights = [face1.shape[0], face2.shape[0]]
    scales_to_full_width = [canvas_w / max(1.0, w) for w in widths]
    h_at_full_width = [int(round(h * s)) for h, s in zip(heights, scales_to_full_width)]

    total_h_full = sum(h_at_full_width) + gap_px + margin_top + margin_bottom

    if total_h_full <= canvas_h:
        tw = [canvas_w, canvas_w]
        th = h_at_full_width
    else:
        available = canvas_h - (margin_top + margin_bottom) - gap_px
        sum_blocks = sum(h_at_full_width)
        global_scale = max(0.05, available / max(1, sum_blocks))
        tw = [max(1, int(round(canvas_w * global_scale))), max(1, int(round(canvas_w * global_scale)))]
        th = [max(1, int(round(h * global_scale))) for h in h_at_full_width]

    y = margin_top
    for img, w_target, h_target in [(face1, tw[0], th[0]), (face2, tw[1], th[1])]:
        interp = cv2.INTER_AREA if (w_target < img.shape[1] or h_target < img.shape[0]) else cv2.INTER_CUBIC
        resized = cv2.resize(img, (w_target, h_target), interpolation=interp)
        x = (canvas_w - w_target) // 2
        canvas = paste_transparent(canvas, resized, x, y)
        y += h_target + gap_px

    return canvas

def _create_three_faces_composite(p1_data: Dict, p2_data: Dict, p3_data: Dict) -> np.ndarray:
    """
    Stacks three extracted faces vertically on a TikTok-sized canvas (no aspect distortion).
    Parents (1 and 3) share the same width; the child (2) is CENTER_MIDDLE_SCALE_3 of that width.
    """
    face1_rgba = _extract_face_rgba(p1_data)
    face2_rgba = _extract_face_rgba(p2_data)
    face3_rgba = _extract_face_rgba(p3_data)

    canvas_w = TIKTOK_CANVAS_W
    canvas_h = TIKTOK_CANVAS_H

    if DYNAMIC_BG_FILL:
        bg_color = _estimate_uniform_bg_color_from_borders(face1_rgba[:, :, :3])
    else:
        bg_color = TIKTOK_BG_FALLBACK_BGR

    canvas = np.full((canvas_h, canvas_w, 3), bg_color, dtype=np.uint8)

    gap = max(8, int(round(canvas_h * VERTICAL_GAP_RATIO)))
    margin_top = max(12, int(round(canvas_h * VERTICAL_MARGIN_RATIO)))
    margin_bottom = margin_top

    s = CENTER_MIDDLE_SCALE_3  # child width ratio relative to parents
    # Fit by height budget:
    # total_h = h1(Wp) + h2(Wp*s) + h3(Wp) + gaps + margins <= canvas_h
    # where hi(W) = (H_i/W_i) * W  -> we estimate via original aspect.
    def h_at_width(img_rgba: np.ndarray, target_w: int) -> int:
        h, w = img_rgba.shape[:2]
        scale = target_w / float(max(1, w))
        return max(1, int(round(h * scale)))

    available_h = canvas_h - (margin_top + margin_bottom + 2 * gap)
    # Start with full width for parents
    Wp = canvas_w
    h1 = h_at_width(face1_rgba, Wp)
    h2 = h_at_width(face2_rgba, int(round(Wp * s)))
    h3 = h_at_width(face3_rgba, Wp)
    total = h1 + h2 + h3

    if total > available_h:
        scale_down = available_h / float(max(1, total))
        Wp = max(1, int(round(Wp * scale_down)))

    Wc = max(1, int(round(Wp * s)))

    def resize_to_width(img_rgba: np.ndarray, target_w: int) -> np.ndarray:
        h, w = img_rgba.shape[:2]
        scale = target_w / float(max(1, w))
        new_w = target_w
        new_h = max(1, int(round(h * scale)))
        interp = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_CUBIC
        return cv2.resize(img_rgba, (new_w, new_h), interpolation=interp)

    face1_r = resize_to_width(face1_rgba, Wp)
    face2_r = resize_to_width(face2_rgba, Wc)
    face3_r = resize_to_width(face3_rgba, Wp)

    y = margin_top
    for i, face in enumerate([face1_r, face2_r, face3_r]):
        fh, fw = face.shape[:2]
        x = (canvas_w - fw) // 2
        canvas = paste_transparent(canvas, face, x, y)
        y += fh
        if i < 2:  # gaps between
            y += gap

    return canvas

# --- Main Function ---

def create_composite_image(*p_bytes_list: bytes) -> Tuple[Optional[bytes], Optional[bytes], Optional[bytes], Optional[bytes]]:
    """
    Builds vertical composites from two or three source photos.
    Returns (all on TikTok canvas):
        1) vertical composite of 2 or 3 people,
        2) portrait of person #1,
        3) portrait of person #2,
        4) portrait of middle person if present, else None.

    On any failure returns (None, None, None, None).
    """
    if not (2 <= len(p_bytes_list) <= 3):
        logger.error("Unsupported number of images for composite", count=len(p_bytes_list))
        return None, None, None, None

    try:
        # 1) Load originals
        p_bgr_list = [load_image_bgr_from_bytes(b) for b in p_bytes_list]
        if any(img is None for img in p_bgr_list):
            return None, None, None, None

        # 2) Analyze + initial scale normalization (kept from your pipeline)
        person_data_raw = [analyze_and_segment_person(bgr) for bgr in p_bgr_list]

        scales = [
            clamp(TARGET_FACE_METRIC_PX / (face_scale_metric(d) or TARGET_FACE_METRIC_PX), MIN_SCALE, MAX_SCALE)
            for d in person_data_raw
        ]
        scaled_bgrs = [_resize(bgr, scale) for bgr, scale in zip(p_bgr_list, scales)]
        scaled_data = [analyze_and_segment_person(bgr) for bgr in scaled_bgrs]
        processed_people = [_rotate_build_rgba_and_stats(d) for d in scaled_data]

        num_people = len(processed_people)

        # 3) Reorder for 3-people layout: parents first, child in the middle
        if num_people == 3:
            processed_people = [processed_people[0], processed_people[2], processed_people[1]]

        # 4) MAIN COMPOSITE from the SAME face crops as portraits
        if num_people == 2:
            final_image_tiktok_bgr = _create_faces_only_composite(processed_people[0], processed_people[1])
        else:  # num_people == 3
            final_image_tiktok_bgr = _create_three_faces_composite(
                processed_people[0], processed_people[1], processed_people[2]
            )

        vertical_composite_jpeg = convert_bgr_to_jpeg_bytes(final_image_tiktok_bgr)

        # 5) Individual portraits (strictly same face crops)
        faces_rgba = [_extract_face_rgba(pp) for pp in processed_people]

        p1_bgr = _fit_face_rgba_to_tiktok_bgr(faces_rgba[0])
        p2_bgr = _fit_face_rgba_to_tiktok_bgr(faces_rgba[-1])
        p1_portrait_jpeg = convert_bgr_to_jpeg_bytes(p1_bgr)
        p2_portrait_jpeg = convert_bgr_to_jpeg_bytes(p2_bgr)

        child_portrait_jpeg: Optional[bytes] = None
        if num_people == 3:
            # After reordering, index 1 is the child (middle).
            child_bgr = _fit_face_rgba_to_tiktok_bgr(faces_rgba[1])
            child_portrait_jpeg = convert_bgr_to_jpeg_bytes(child_bgr)

        return vertical_composite_jpeg, p1_portrait_jpeg, p2_portrait_jpeg, child_portrait_jpeg

    except Exception:
        logger.exception("A critical error occurred in create_composite_image.")
        return None, None, None, None
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
    10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288, 397, 365, 379, 378, 400, 377, 152, 148, 176, 149, 150, 136, 172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109
]

# --- Pipeline parameters ---
TARGET_FACE_METRIC_PX = 220.0
MIN_SCALE, MAX_SCALE = 0.60, 1.80
SEGMENTATION_THRESHOLD = 0.10
OVERLAP_RATIO = 0.30
HEAD_MARGIN_RATIO_OF_HEADH = 0.12
HEAD_MARGIN_PX_MIN = 18
HEAD_STRIP_TOP_EXTRA = 0.25
HEAD_STRIP_BOTTOM_EXTRA = 0.10
SEAM_SOFTEN_PX = 26
SEAM_SOFTEN_SIGMA = 6.0
CROP_ASPECT = 0.75

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
    rot_bgr = cv2.warpAffine(img_bgr, M, (w, h), flags=cv2.INTER_LINEAR, borderValue=(0,0,0))
    rot_rgba = cv2.warpAffine(person_rgba, M, (w, h), flags=cv2.INTER_LINEAR, borderValue=(0,0,0,0))
    eyes_rot = M @ np.array([center_eyes[0], center_eyes[1], 1.0], dtype=np.float32)
    lm_hom = np.hstack([lm_px, np.ones((lm_px.shape[0], 1))])
    rotated_landmarks = (M @ lm_hom.T).T
    a = rot_rgba[:, :, 3]
    ys, xs = np.where(a > 10)
    top_y, bot_y = (int(ys.min()), int(ys.max())) if len(ys) > 0 else (0, h - 1)
    return {
        "rot_bgr": rot_bgr, "rot_rgba": rot_rgba, "eyes_xy": (float(eyes_rot[0]), float(eyes_rot[1])),
        "head_h": float(np.linalg.norm(lm_px[FOREHEAD_TOP] - lm_px[CHIN_BOTTOM])),
        "clearances": {"up": float(eyes_rot[1] - top_y), "down": float(bot_y - eyes_rot[1])},
        "rot_landmarks": rotated_landmarks
    }

def _extract_face_rgba(data: Dict) -> np.ndarray:
    """Extracts a soft-edged, cropped RGBA face using landmarks for child generation."""
    img_bgr, h, w = data["rot_bgr"], *data["rot_bgr"].shape[:2]
    landmarks = data["rot_landmarks"]
    oval_points = landmarks[FACE_OVAL_LANDMARK_INDICES].astype(np.int32)
    x, y, bw, bh = cv2.boundingRect(oval_points)
    pad = int(max(bw, bh) * 0.15)
    x1, y1 = max(0, x - pad), max(0, y - pad)
    x2, y2 = min(w, x + bw + pad), min(h, y + bh + pad)
    cropped_bgr = img_bgr[y1:y2, x1:x2]
    oval_points_cropped = oval_points - np.array([x1, y1])
    mask = np.zeros(cropped_bgr.shape[:2], dtype=np.uint8)
    cv2.fillConvexPoly(mask, cv2.convexHull(oval_points_cropped), 255)
    mask = cv2.GaussianBlur(mask, (31, 31), 10)
    face_rgba = cv2.cvtColor(cropped_bgr, cv2.COLOR_BGR2BGRA)
    face_rgba[:, :, 3] = mask
    return face_rgba

def _convert_rgba_to_bgr_on_solid_bg(img_rgba: np.ndarray, bg_color=(128, 128, 128)) -> np.ndarray:
    """Pastes an RGBA image onto a solid background, returning a BGR image."""
    h, w = img_rgba.shape[:2]
    background = np.full((h, w, 3), bg_color, dtype=np.uint8)
    return paste_transparent(background, img_rgba, 0, 0)

def _create_faces_only_composite(p1_data: Dict, p2_data: Dict) -> np.ndarray:
    """Creates the faces-only composite specifically for the child generation pipeline."""
    face1_rgba, face2_rgba = _extract_face_rgba(p1_data), _extract_face_rgba(p2_data)
    h1, w1 = face1_rgba.shape[:2]
    h2, w2 = face2_rgba.shape[:2]
    y_offset = (h1 // 2) - (h2 // 2)
    margin = int(max(p1_data['head_h'], p2_data['head_h']) * 0.20)
    canvas_w = w1 + w2 + margin
    canvas_h = max(h1 + abs(y_offset) if y_offset < 0 else h1, h2 + abs(y_offset) if y_offset > 0 else h2) + margin * 2
    canvas = np.full((int(canvas_h), int(canvas_w), 3), 128, dtype=np.uint8)
    paste_y1, paste_x1 = margin + max(0, -y_offset), 0
    paste_y2, paste_x2 = margin + max(0, y_offset), w1 + margin
    canvas = paste_transparent(canvas, face1_rgba, paste_x1, paste_y1)
    canvas = paste_transparent(canvas, face2_rgba, paste_x2, paste_y2)
    return canvas

def _create_three_faces_composite(p1_data: Dict, p2_data: Dict, p3_data: Dict) -> np.ndarray:
    """Creates a side-by-side composite of three extracted faces for family portraits."""
    # The order is assumed to be Father, Child, Mother
    face1_rgba = _extract_face_rgba(p1_data)
    face2_rgba = _extract_face_rgba(p2_data)
    face3_rgba = _extract_face_rgba(p3_data)

    faces = [face1_rgba, face2_rgba, face3_rgba]
    heights = [f.shape[0] for f in faces]
    max_h = max(heights)

    # Resize faces to have the same height for cleaner alignment, preserving aspect ratio
    resized_faces = []
    for face in faces:
        h, w = face.shape[:2]
        if h != max_h:
            scale = max_h / h
            new_w = int(w * scale)
            resized_faces.append(cv2.resize(face, (new_w, max_h), interpolation=cv2.INTER_LANCZOS4))
        else:
            resized_faces.append(face)

    widths = [f.shape[1] for f in resized_faces]
    margin = int(max_h * 0.10)  # 10% margin between faces

    canvas_w = sum(widths) + (margin * 2)  # Margins between 3 faces
    canvas_h = max_h

    # Create a neutral gray background
    canvas = np.full((canvas_h, canvas_w, 3), 128, dtype=np.uint8)

    current_x = 0
    for face in resized_faces:
        # y_offset should be 0 since all are max_h
        canvas = paste_transparent(canvas, face, current_x, 0)
        current_x += face.shape[1] + margin

    return canvas
    
def _resize(img: np.ndarray, scale: float) -> np.ndarray:
    """Resizes an image using an appropriate interpolation method."""
    if abs(scale - 1.0) < 1e-3: return img
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
        x1 += pad_left; y1 += pad_top
    return img[y1:y2, x1:x2], pad_left, pad_top

def _soften_vertical_band(img_bgr: np.ndarray, cx: int, width: int, sigma: float) -> None:
    """Applies a vertical Gaussian blur to a specific band of the image to hide seams."""
    if width <= 0: return
    h, w = img_bgr.shape[:2]
    x0 = max(0, int(cx - width // 2)); x1 = min(w, int(cx + (width + 1) // 2))
    if x1 <= x0: return
    roi = img_bgr[:, x0:x1]
    blurred = cv2.GaussianBlur(roi, ksize=(0, 0), sigmaX=sigma, sigmaY=0)
    img_bgr[:, x0:x1] = blurred

# --- Main Function ---

def create_composite_image(*p_bytes_list: bytes) -> Tuple[Optional[bytes], Optional[bytes], Optional[bytes], Optional[bytes]]:
    """
    Builds a composite image from two or three source photos.
    The order of people in the composite is the same as the order of bytes passed.

    Args:
        *p_bytes_list: Two or three byte strings of the source images.

    Returns:
        A tuple of four items, maintaining a consistent signature:
        - For 2 people: (composite_jpeg, faces_only_jpeg, person1_face_jpeg, person2_face_jpeg)
        - For 3 people: (composite_jpeg, three_faces_jpeg, None, None)
        Returns (None, None, None, None) on any failure.
    """
    if not (2 <= len(p_bytes_list) <= 3):
        logger.error("Unsupported number of images for composite", count=len(p_bytes_list))
        return None, None, None, None

    try:
        # --- 1. Preprocessing (Common for 2 or 3 people) ---
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
        
        cropped_bgs = []
        cropped_persons_rgba = []
        for p_data in processed_people:
            ex, ey = p_data["eyes_xy"]
            x1, y1 = int(round(ex - crop_w / 2)), int(round(ey - up_common))
            x2, y2 = x1 + crop_w, y1 + crop_h
            bg_crop, _, _ = _pad_crop_with_offsets(p_data["rot_bgr"], x1, y1, x2, y2)
            person_rgba_crop, _, _ = _pad_crop_with_offsets(p_data["rot_rgba"], x1, y1, x2, y2)
            cropped_bgs.append(bg_crop)
            cropped_persons_rgba.append(person_rgba_crop)

        # --- 3. Main Composite (Common for 2 or 3 people) ---
        overlap_px = int(crop_w * OVERLAP_RATIO)
        final_w = sum(bg.shape[1] for bg in cropped_bgs) - (overlap_px * (num_people - 1))
        
        composite_bg = np.zeros((crop_h, final_w, 3), dtype=np.uint8)
        current_x = 0
        for i, bg in enumerate(cropped_bgs):
            w_i = bg.shape[1]
            if i == 0:
                composite_bg[:, :w_i] = bg
            else:
                paste_x = current_x
                alpha = np.linspace(0, 1, overlap_px, dtype=np.float32).reshape(1, -1, 1)
                left_zone = composite_bg[:, paste_x : paste_x + overlap_px].astype(np.float32)
                right_zone = bg[:, :overlap_px].astype(np.float32)
                blended = left_zone * (1.0 - alpha) + right_zone * alpha
                composite_bg[:, paste_x : paste_x + overlap_px] = np.clip(blended, 0, 255)
                composite_bg[:, paste_x + overlap_px : paste_x + w_i] = bg[:, overlap_px:]
                _soften_vertical_band(composite_bg, paste_x, SEAM_SOFTEN_PX, SEAM_SOFTEN_SIGMA)
            current_x += w_i - overlap_px
            
        final_image = composite_bg.copy()

        # --- MODIFICATION START ---
        # Pre-calculate paste positions for all persons to handle layering correctly.
        paste_positions = []
        current_x_pos = 0
        for i in range(num_people):
            paste_positions.append(current_x_pos)
            current_x_pos += cropped_bgs[i].shape[1] - overlap_px

        # For a 3-person family portrait, paste the child (center) last so they appear in front.
        if num_people == 3:
            # Paste parents first (Father at index 0, Mother at index 2)
            final_image = paste_transparent(final_image, cropped_persons_rgba[0], paste_positions[0], 0)
            final_image = paste_transparent(final_image, cropped_persons_rgba[2], paste_positions[2], 0)
            # Paste child last (index 1) so they are on top of any overlap
            final_image = paste_transparent(final_image, cropped_persons_rgba[1], paste_positions[1], 0)
        else:
            # Default behavior for 2 people (sequential paste is fine)
            for i, person_rgba in enumerate(cropped_persons_rgba):
                 final_image = paste_transparent(final_image, person_rgba, paste_positions[i], 0)
        # --- MODIFICATION END ---
        
        composite_jpeg = convert_bgr_to_jpeg_bytes(final_image)

        # --- 4. Generate case-specific additional outputs ---
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
            # The order of processed_people is Father, Child, Mother
            p1, p2, p3 = processed_people[0], processed_people[1], processed_people[2]
            three_faces_bgr = _create_three_faces_composite(p1, p2, p3)
            faces_only_jpeg = convert_bgr_to_jpeg_bytes(three_faces_bgr)

        return composite_jpeg, faces_only_jpeg, p1_face_jpeg, p2_face_jpeg

    except Exception:
        logger.exception("A critical error occurred in create_composite_image.")
        return None, None, None, None 
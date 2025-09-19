# aiogram_bot_template/services/photo_processing.py
import cv2
import io
import uuid
import mediapipe as mp
import numpy as np
import structlog
from typing import Optional, Tuple, Dict
from PIL import Image, ImageOps

logger = structlog.get_logger(__name__)

# --- MediaPipe setup ---
mp_face_mesh = mp.solutions.face_mesh
mp_selfie_segmentation = mp.solutions.selfie_segmentation

# FaceMesh landmark indices
FOREHEAD_TOP, CHIN_BOTTOM = 10, 152
LEFT_EYE_OUTER, RIGHT_EYE_OUTER = 263, 33
LEFT_FACE_OUTER, RIGHT_FACE_OUTER = 234, 454  # cheek extremes

# Indices for the face oval contour, used for the faces-only composite
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
EDGE_BLUR_KSIZE = 99
CROP_ASPECT = 0.75
DEBUG_OVERLAYS = True


# --- I/O ---

def load_image_bgr_from_bytes(data: bytes) -> Optional[np.ndarray]:
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
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    buf = io.BytesIO()
    Image.fromarray(img_rgb).save(buf, format="JPEG", quality=quality, optimize=True)
    return buf.getvalue()


def paste_transparent(background: np.ndarray, foreground: np.ndarray, x: int, y: int) -> np.ndarray:
    """Alpha-composite RGBA foreground over BGR background at (x, y)."""
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
    """Return image, face landmarks and person segmentation mask."""
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)

    with mp_face_mesh.FaceMesh(
        static_image_mode=True, max_num_faces=1, refine_landmarks=False, min_detection_confidence=0.5
    ) as fm:
        res = fm.process(img_rgb)
        if not res.multi_face_landmarks:
            raise ValueError("Face not found.")
        face_lm = res.multi_face_landmarks[0]

    with mp_selfie_segmentation.SelfieSegmentation(model_selection=0) as seg:
        seg_mask = seg.process(img_rgb).segmentation_mask

    return {"image_bgr": img_bgr, "face_landmarks": face_lm, "segmentation_mask": seg_mask}


def _lm_to_px(face_lm, w: int, h: int) -> np.ndarray:
    return np.array([(p.x * w, p.y * h) for p in face_lm.landmark], dtype=np.float32)


def get_interocular_distance(person_data: Dict) -> Optional[float]:
    img = person_data["image_bgr"]; h, w = img.shape[:2]
    lm = _lm_to_px(person_data["face_landmarks"], w, h)
    return float(np.linalg.norm(lm[LEFT_EYE_OUTER] - lm[RIGHT_EYE_OUTER]))


def get_head_height(person_data: Dict) -> Optional[float]:
    img = person_data["image_bgr"]; h, w = img.shape[:2]
    lm = _lm_to_px(person_data["face_landmarks"], w, h)
    return float(np.linalg.norm(lm[FOREHEAD_TOP] - lm[CHIN_BOTTOM]))


def face_scale_metric(person_data: Dict) -> Optional[float]:
    iod = get_interocular_distance(person_data)
    hh = get_head_height(person_data)
    if not iod or not hh or iod <= 0 or hh <= 0:
        return None
    return float(np.sqrt(iod * hh))

def _rotate_build_rgba_and_stats(person_data: Dict) -> Dict:
    img_bgr = person_data["image_bgr"]
    mask = person_data["segmentation_mask"]
    h, w = img_bgr.shape[:2]

    condition = np.stack((mask,) * 3, axis=-1) > SEGMENTATION_THRESHOLD
    person_bgr = np.where(condition, img_bgr, 0)
    alpha_channel = (np.clip(mask, 0.0, 1.0) * 255).astype(np.uint8)
    person_rgba = cv2.merge([*cv2.split(person_bgr), alpha_channel])

    lm_px = _lm_to_px(person_data["face_landmarks"], w, h)
    p_le, p_re = lm_px[LEFT_EYE_OUTER], lm_px[RIGHT_EYE_OUTER]
    angle_deg = float(np.degrees(np.arctan2(p_le[1] - p_re[1], p_le[0] - p_re[0])))
    center_eyes = (p_le + p_re) / 2.0
    head_height = float(np.linalg.norm(lm_px[FOREHEAD_TOP] - lm_px[CHIN_BOTTOM]))

    M = cv2.getRotationMatrix2D((float(center_eyes[0]), float(center_eyes[1])), angle_deg, 1.0)
    rot_bgr = cv2.warpAffine(img_bgr, M, (w, h), flags=cv2.INTER_LINEAR, borderValue=(0, 0, 0))
    rot_rgba = cv2.warpAffine(person_rgba, M, (w, h), flags=cv2.INTER_LINEAR, borderValue=(0, 0, 0, 0))
    eyes_rot = M @ np.array([center_eyes[0], center_eyes[1], 1.0], dtype=np.float32)
    lm_hom = np.hstack([lm_px, np.ones((lm_px.shape[0], 1))])
    rotated_landmarks = (M @ lm_hom.T).T

    rot_pts = {
        "forehead": rotated_landmarks[FOREHEAD_TOP], "chin": rotated_landmarks[CHIN_BOTTOM],
        "cheek_L": rotated_landmarks[LEFT_FACE_OUTER], "cheek_R": rotated_landmarks[RIGHT_FACE_OUTER],
    }
    
    a = rot_rgba[:, :, 3]
    ys, xs = np.where(a > 10)
    top_y, bot_y, left_x, right_x = (int(ys.min()), int(ys.max()), int(xs.min()), int(xs.max())) if len(ys) > 0 else (0, h - 1, 0, w - 1)

    return {
        "rot_bgr": rot_bgr, "rot_rgba": rot_rgba, "eyes_xy": (float(eyes_rot[0]), float(eyes_rot[1])),
        "head_h": head_height, "angle_deg": angle_deg, "bounds": {"top_y": top_y, "bot_y": bot_y, "left_x": left_x, "right_x": right_x},
        "clearances": {"up": float(eyes_rot[1] - top_y), "down": float(bot_y - eyes_rot[1])},
        "rot_face_pts": rot_pts, "rot_landmarks": rotated_landmarks
    }


def _extract_face_rgba(data: Dict) -> np.ndarray:
    """Extracts a soft-edged, cropped RGBA face using landmarks."""
    img_bgr = data["rot_bgr"]
    h, w = img_bgr.shape[:2]
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


def _create_faces_only_composite(L_data: Dict, R_data: Dict) -> np.ndarray:
    face_L_rgba = _extract_face_rgba(L_data)
    face_R_rgba = _extract_face_rgba(R_data)
    h_L, w_L = face_L_rgba.shape[:2]
    h_R, w_R = face_R_rgba.shape[:2]
    y_offset = (h_L // 2) - (h_R // 2)
    margin = int(max(L_data['head_h'], R_data['head_h']) * 0.20)
    canvas_w = w_L + w_R + margin
    canvas_h = max(h_L + abs(y_offset) if y_offset < 0 else h_L, h_R + abs(y_offset) if y_offset > 0 else h_R) + margin * 2
    canvas = np.full((int(canvas_h), int(canvas_w), 3), 128, dtype=np.uint8)
    paste_y_L = margin + max(0, -y_offset); paste_x_L = 0
    paste_y_R = margin + max(0, y_offset); paste_x_R = w_L + margin
    canvas = paste_transparent(canvas, face_L_rgba, paste_x_L, paste_y_L)
    canvas = paste_transparent(canvas, face_R_rgba, paste_x_R, paste_y_R)
    return canvas

def _resize(img: np.ndarray, scale: float) -> np.ndarray:
    if abs(scale - 1.0) < 1e-3: return img
    interp = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_CUBIC
    h, w = img.shape[:2]; return cv2.resize(img, (int(round(w * scale)), int(round(h * scale))), interpolation=interp)

def _pad_crop_with_offsets(img: np.ndarray, x1: int, y1: int, x2: int, y2: int) -> Tuple[np.ndarray, int, int]:
    h, w = img.shape[:2]; pad_left = max(0, -x1); pad_top = max(0, -y1); pad_right = max(0, x2 - w); pad_bottom = max(0, y2 - h)
    if any(v > 0 for v in (pad_left, pad_top, pad_right, pad_bottom)):
        img = cv2.copyMakeBorder(img, pad_top, pad_bottom, pad_left, pad_right, cv2.BORDER_REPLICATE)
        x1 += pad_left; y1 += pad_top
    return img[y1:y2, x1:x2], pad_left, pad_top

def _soften_vertical_band(img_bgr: np.ndarray, cx: int, width: int, sigma: float) -> None:
    if width <= 0: return
    h, w = img_bgr.shape[:2]; x0 = max(0, int(cx - width // 2)); x1 = min(w, int(cx + (width + 1) // 2))
    if x1 <= x0: return
    roi = img_bgr[:, x0:x1]; blurred = cv2.GaussianBlur(roi, ksize=(0, 0), sigmaX=sigma, sigmaY=0); img_bgr[:, x0:x1] = blurred

def _head_bounds_x_in_crop(rot_rgba: np.ndarray, rot_pts: Dict, x1_orig: int, y1_orig: int, pad_left: int, pad_top: int, crop_w: int, crop_h: int, head_h: float) -> Tuple[int, int]:
    fh, ch = float(rot_pts["forehead"][1]), float(rot_pts["chin"][1]); H, W = rot_rgba.shape[:2]
    y_min = max(0, int(round(min(fh, ch) - HEAD_STRIP_TOP_EXTRA * head_h))); y_max = min(H - 1, int(round(max(fh, ch) + HEAD_STRIP_BOTTOM_EXTRA * head_h)))
    if y_max <= y_min: y_min, y_max = max(0, int(min(fh, ch))), min(H - 1, int(max(fh, ch)))
    x1, y1 = x1_orig - pad_left, y1_orig - pad_top; x2, y2 = x1 + crop_w, y1 + crop_h
    ys, xs = slice(max(y_min, y1), min(y_max + 1, y2)), slice(max(x1, 0), min(x2, W))
    cols = np.where(rot_rgba[ys, xs][:, :, 3] > 10)[1]
    if cols.size == 0:
        xmin = max(0, min(int(round(float(rot_pts["cheek_L"][0]) - x1)), int(round(float(rot_pts["cheek_R"][0]) - x1))))
        xmax = min(crop_w - 1, max(int(round(float(rot_pts["cheek_L"][0]) - x1)), int(round(float(rot_pts["cheek_R"][0]) - x1))))
    else: xmin, xmax = int(cols.min()), int(cols.max())
    return int(np.clip(xmin, 0, crop_w - 1)), int(np.clip(xmax, 0, crop_w - 1))

# --- Main ---

def create_composite_image(p1_bytes: bytes, p2_bytes: bytes) -> Tuple[Optional[bytes], Optional[bytes], Optional[bytes], Optional[bytes]]:
    """
    Builds a primary composite, a faces-only composite, and individual face crops.

    Args:
        p1_bytes: Bytes of the mother's photo (will be placed on the right).
        p2_bytes: Bytes of the father's photo (will be placed on the left).

    Returns:
        A tuple of four items:
        1. composite_jpeg: The main blended image.
        2. faces_only_jpeg: A composite of just the two faces.
        3. mom_face_jpeg: A cropped image of just the mother's face.
        4. dad_face_jpeg: A cropped image of just the father's face.
        Returns (None, None, None, None) on failure.
    """
    p1_bgr = load_image_bgr_from_bytes(p1_bytes)  # mother
    p2_bgr = load_image_bgr_from_bytes(p2_bytes)  # father
    if p1_bgr is None or p2_bgr is None:
        return None, None, None, None

    try:
        d2 = analyze_and_segment_person(p2_bgr); d1 = analyze_and_segment_person(p1_bgr)
        s2 = face_scale_metric(d2); s1 = face_scale_metric(d1)
        scale2 = clamp(TARGET_FACE_METRIC_PX / s2, MIN_SCALE, MAX_SCALE) if s2 else 1.0
        scale1 = clamp(TARGET_FACE_METRIC_PX / s1, MIN_SCALE, MAX_SCALE) if s1 else 1.0
        p2s = _resize(p2_bgr, scale2); p1s = _resize(p1_bgr, scale1)
        d2s = analyze_and_segment_person(p2s); d1s = analyze_and_segment_person(p1s)

        L = _rotate_build_rgba_and_stats(d2s); R = _rotate_build_rgba_and_stats(d1s)

        # --- 1. Generate the faces-only composite ---
        faces_only_composite_bgr = _create_faces_only_composite(L, R)

        # --- 2. Generate the individual face crops ---
        mom_face_rgba = _extract_face_rgba(R)
        dad_face_rgba = _extract_face_rgba(L)
        mom_face_bgr = _convert_rgba_to_bgr_on_solid_bg(mom_face_rgba)
        dad_face_bgr = _convert_rgba_to_bgr_on_solid_bg(dad_face_rgba)
        
        # --- 3. Generate the full scene composite ---
        head_h_avg = float((L["head_h"] + R["head_h"]) / 2.0)
        up_common = float(np.clip(min(L["clearances"]["up"], R["clearances"]["up"]), 0.6 * head_h_avg, 1.3 * head_h_avg))
        down_common = float(np.clip(min(L["clearances"]["down"], R["clearances"]["down"]), 0.8 * head_h_avg, 3.0 * head_h_avg))
        crop_h = int(round(up_common + down_common)); crop_w = int(round(crop_h * CROP_ASPECT))

        # THIS IS THE FIX: The nested function now returns 5 values
        def crop_from_eyes(img, eyes_xy):
            ex, ey = eyes_xy
            x1 = int(round(ex - crop_w / 2))
            y1 = int(round(ey - up_common))
            x2 = x1 + crop_w
            y2 = y1 + crop_h
            crop, pad_left, pad_top = _pad_crop_with_offsets(img, x1, y1, x2, y2)
            return crop, x1, y1, pad_left, pad_top

        left_bg, lx1, ly1, lpadx, lpady = crop_from_eyes(L["rot_bgr"], L["eyes_xy"])
        right_bg, rx1, ry1, rpadx, rpady = crop_from_eyes(R["rot_bgr"], R["eyes_xy"])
        left_person_rgba, _, _, _, _ = crop_from_eyes(L["rot_rgba"], L["eyes_xy"])
        right_person_rgba, _, _, _, _ = crop_from_eyes(R["rot_rgba"], R["eyes_xy"])

        lhx0, lhx1 = _head_bounds_x_in_crop(L["rot_rgba"], L["rot_face_pts"], lx1, ly1, lpadx, lpady, left_bg.shape[1], left_bg.shape[0], L["head_h"])
        rhx0, rhx1 = _head_bounds_x_in_crop(R["rot_rgba"], R["rot_face_pts"], rx1, ry1, rpadx, rpady, right_bg.shape[1], right_bg.shape[0], R["head_h"])

        head_margin_px = int(max(HEAD_MARGIN_PX_MIN, HEAD_MARGIN_RATIO_OF_HEADH * head_h_avg))
        base_overlap = int(min(left_bg.shape[1], right_bg.shape[1]) * OVERLAP_RATIO)
        adjust = head_margin_px - ((left_bg.shape[1] - base_overlap + rhx0) - lhx1)
        overlap_px = int(np.clip(base_overlap - int(round(adjust)), -min(64, max(left_bg.shape[1], right_bg.shape[1])), min(left_bg.shape[1], right_bg.shape[1])))
        right_x = left_bg.shape[1] - overlap_px

        final_w = left_bg.shape[1] + right_bg.shape[1] - overlap_px
        composite_bg = np.zeros((crop_h, final_w, 3), dtype=np.uint8)
        composite_bg[:, :left_bg.shape[1]] = left_bg
        if overlap_px > 0:
            alpha = np.linspace(0, 1, overlap_px, dtype=np.float32).reshape(1, -1, 1)
            left_zone = composite_bg[:, right_x:right_x+overlap_px].astype(np.float32)
            right_zone = right_bg[:, :overlap_px].astype(np.float32)
            blended = left_zone * (1.0 - alpha) + right_zone * alpha
            composite_bg[:, right_x:right_x+overlap_px] = np.clip(blended, 0, 255)
            composite_bg[:, right_x+overlap_px:] = right_bg[:, overlap_px:]
        else: composite_bg[:, right_x:right_x+right_bg.shape[1]] = right_bg

        _soften_vertical_band(composite_bg, right_x, SEAM_SOFTEN_PX, SEAM_SOFTEN_SIGMA)
        final_image = paste_transparent(composite_bg, left_person_rgba, 0, 0)
        final_image = paste_transparent(final_image, right_person_rgba, right_x, 0)

        # --- 4. Encode all outputs ---
        composite_jpeg = convert_bgr_to_jpeg_bytes(final_image)
        faces_only_jpeg = convert_bgr_to_jpeg_bytes(faces_only_composite_bgr)
        mom_face_jpeg = convert_bgr_to_jpeg_bytes(mom_face_bgr)
        dad_face_jpeg = convert_bgr_to_jpeg_bytes(dad_face_bgr)

        return composite_jpeg, faces_only_jpeg, mom_face_jpeg, dad_face_jpeg

    except Exception:
        logger.exception("A critical error occurred in create_composite_image.")
        return None, None, None, None

def crop_generated_image(image_bytes: bytes) -> Tuple[Optional[bytes], Optional[bytes]]:
    """Split the final composite in two halves."""
    try:
        img_np = load_image_bgr_from_bytes(image_bytes)
        if img_np is None: return None, None
        h, w, _ = img_np.shape; midpoint = w // 2
        return convert_bgr_to_jpeg_bytes(img_np[:, :midpoint]), convert_bgr_to_jpeg_bytes(img_np[:, midpoint:])
    except Exception:
        logger.exception("Failed to crop generated image.")
        return None, None
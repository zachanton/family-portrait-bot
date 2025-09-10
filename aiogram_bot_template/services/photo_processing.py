# aiogram_bot_template/services/photo_processing.py
import cv2
import io
import mediapipe as mp
import numpy as np
import structlog
from typing import Optional, Tuple
from PIL import Image, ImageOps
from dataclasses import dataclass

logger = structlog.get_logger(__name__)

@dataclass
class ProcessedImageOutput:
    """A data class to hold all generated crop versions of a processed image."""
    headshot: bytes
    portrait: bytes
    half_body: bytes

# ------------------------------
# Constants and Key Landmark Indices
# ------------------------------
RIGHT_EYE_OUTER = 33; LEFT_EYE_OUTER = 263; CHIN_BOTTOM = 152; FOREHEAD_TOP = 10
CROP_PARAMS = {"headshot": (0.65, 0.15), "portrait": (0.50, 0.20), "half_body": (0.35, 0.18)}

# ------------------------------
# I/O and Image Conversion
# ------------------------------
def load_image_bgr_from_bytes(data: bytes) -> Optional[np.ndarray]:
    try:
        img = Image.open(io.BytesIO(data)); img = ImageOps.exif_transpose(img)
        return cv2.cvtColor(np.asarray(img.convert("RGB")), cv2.COLOR_RGB2BGR)
    except Exception:
        logger.exception("Failed to load image from bytes"); return None

def convert_bgr_to_jpeg_bytes(img_bgr: np.ndarray, quality: int = 90) -> bytes:
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB); pil_img = Image.fromarray(img_rgb)
    buffer = io.BytesIO(); pil_img.save(buffer, format="JPEG", quality=quality, optimize=True)
    return buffer.getvalue()

# ---------------------------------------------
# Face Landmark Detection
# ---------------------------------------------
def detect_face_landmarks(img_bgr: np.ndarray) -> np.ndarray:
    h, w = img_bgr.shape[:2]; img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    with mp.solutions.face_mesh.FaceMesh(static_image_mode=True, max_num_faces=1, refine_landmarks=True, min_detection_confidence=0.5) as fm:
        res = fm.process(img_rgb)
    if not res.multi_face_landmarks: raise RuntimeError("Face landmarks not found.")
    lmk = res.multi_face_landmarks[0].landmark
    return np.array([(p.x * w, p.y * h) for p in lmk], dtype=np.float32)

# --------------------------------------------------------------------
# Aspect Ratio-Preserving Alignment and Cropping
# --------------------------------------------------------------------
def align_and_crop_robust(img_bgr: np.ndarray, lmk_px: np.ndarray, output_size: int = 1024, crop_mode: str = "half_body") -> np.ndarray:
    p_right_eye, p_left_eye = lmk_px[RIGHT_EYE_OUTER], lmk_px[LEFT_EYE_OUTER]
    p_chin, p_forehead = lmk_px[CHIN_BOTTOM], lmk_px[FOREHEAD_TOP]
    target_head_height_frac, top_margin_frac = CROP_PARAMS[crop_mode]
    eye_delta = p_left_eye - p_right_eye
    angle_deg = np.degrees(np.arctan2(eye_delta[1], eye_delta[0]))
    points_h = np.array([[p_chin[0], p_forehead[0]], [p_chin[1], p_forehead[1]], [1.0, 1.0]])
    rot_mat_3x3 = np.vstack([cv2.getRotationMatrix2D((0,0), angle_deg, 1.0), [0, 0, 1]])
    rotated_head_points = np.dot(rot_mat_3x3, points_h)[:2, :]
    current_head_height = abs(rotated_head_points[1, 0] - rotated_head_points[1, 1]) or 1.0
    target_head_height = output_size * target_head_height_frac
    scale = target_head_height / current_head_height
    head_center = (p_chin + p_forehead) / 2.0
    M = cv2.getRotationMatrix2D(tuple(head_center), angle_deg, scale)
    transformed_forehead = np.dot(M, (p_forehead[0], p_forehead[1], 1))
    target_y = output_size * top_margin_frac
    M[1, 2] += target_y - transformed_forehead[1]
    transformed_head_center = np.dot(M, (head_center[0], head_center[1], 1))
    M[0, 2] += (output_size / 2.0) - transformed_head_center[0]
    return cv2.warpAffine(img_bgr, M, (output_size, output_size), flags=cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_CONSTANT, borderValue=(127, 127, 127))

# --------------------------------------------------------------------
# Pair Harmonization and Compositing
# --------------------------------------------------------------------
def _color_transfer(source_bgr: np.ndarray, target_bgr: np.ndarray) -> np.ndarray:
    source = cv2.cvtColor(source_bgr, cv2.COLOR_BGR2LAB).astype("float32")
    target = cv2.cvtColor(target_bgr, cv2.COLOR_BGR2LAB).astype("float32")
    (l_mean_src, _, _), (l_std_src, _, _) = cv2.meanStdDev(source)
    (l_mean_tgt, _, _), (l_std_tgt, _, _) = cv2.meanStdDev(target)
    (l, a, b) = cv2.split(target)
    l -= l_mean_tgt; a -= 0; b -= 0 # Only adjust lightness for natural look
    l = (l_std_src / l_std_tgt) * l
    l += l_mean_src
    l = np.clip(l, 0, 255)
    return cv2.cvtColor(cv2.merge([l, a, b]).astype("uint8"), cv2.COLOR_LAB2BGR)

def harmonize_pair(master_bytes: bytes, slave_bytes: bytes) -> Tuple[bytes, bytes]:
    logger.info("Starting MASTER-SLAVE harmonization...")
    master_img, slave_img = load_image_bgr_from_bytes(master_bytes), load_image_bgr_from_bytes(slave_bytes)
    if master_img is None or slave_img is None: return master_bytes, slave_bytes
    try:
        corrected_slave = _color_transfer(master_img, slave_img)
        logger.info("Master-slave harmonization finished successfully.")
        return (master_bytes, convert_bgr_to_jpeg_bytes(corrected_slave))
    except Exception:
        logger.exception("Harmonization failed."); return master_bytes, slave_bytes

def _create_person_mask(image: np.ndarray) -> Optional[np.ndarray]:
    try:
        landmarks = detect_face_landmarks(image)
        face_oval_indices = [10,338,297,332,284,251,389,356,454,323,361,288,397,365,379,378,400,377,152,148,176,149,150,136,172,58,132,93,234,127,162,21,54,103,67,109]
        hull = cv2.convexHull(landmarks[face_oval_indices].astype(np.int32))
        x, y, w, h = cv2.boundingRect(hull)
        mask = np.zeros(image.shape[:2], dtype=np.uint8)
        cv2.ellipse(mask, (x+w//2, y+h//2), (int(w*0.9), int(h*1.3)), 0, 0, 360, 255, -1)
        return cv2.GaussianBlur(mask, (199, 199), 0)
    except Exception:
        return None

def _create_gradient_background(width: int, height: int, top_color=(230, 220, 210), bottom_color=(200, 190, 180)) -> np.ndarray:
    background = np.zeros((height, width, 3), dtype=np.float32)
    for y in range(height):
        alpha = y / (height - 1)
        color = [(1 - alpha) * c1 + alpha * c2 for c1, c2 in zip(top_color, bottom_color)]
        background[y, :] = color
    noise = np.random.randn(height, width, 3) * 2; background += noise
    return np.clip(background, 0, 255).astype(np.uint8)

def _paste_bgra_on_bgr(foreground_bgra: np.ndarray, background_bgr: np.ndarray, x: int, y: int) -> np.ndarray:
    fh, fw = foreground_bgra.shape[:2]
    bh, bw = background_bgr.shape[:2]

    # Ensure the paste location is valid
    if x >= bw or y >= bh or x + fw <= 0 or y + fh <= 0:
        return background_bgr

    # Clip coordinates to be within background bounds
    x1, y1 = max(x, 0), max(y, 0)
    x2, y2 = min(x + fw, bw), min(y + fh, bh)
    
    fg_x1, fg_y1 = max(0, -x), max(0, -y)
    fg_x2, fg_y2 = fw - max(0, (x + fw) - bw), fh - max(0, (y + fh) - bh)

    if y2 <= y1 or x2 <= x1:
        return background_bgr

    roi_bg = background_bgr[y1:y2, x1:x2]
    roi_fg = foreground_bgra[fg_y1:fg_y2, fg_x1:fg_x2]

    alpha = (roi_fg[:, :, 3].astype(np.float32) / 255.0)[:, :, np.newaxis]
    blended = roi_bg * (1.0 - alpha) + roi_fg[:, :, :3] * alpha
    background_bgr[y1:y2, x1:x2] = blended.astype(np.uint8)
    return background_bgr

def create_composite_image(person1_bytes: bytes, person2_bytes: bytes) -> bytes:
    logger.info("Starting FINAL Alpha Composite creation...")
    p1_img, p2_img = load_image_bgr_from_bytes(person1_bytes), load_image_bgr_from_bytes(person2_bytes)
    if p1_img is None or p2_img is None: return person1_bytes

    canvas_w, canvas_h = 1024, 1280
    background = _create_gradient_background(canvas_w, canvas_h)

    mask1 = _create_person_mask(p1_img); mask2 = _create_person_mask(p2_img)
    if mask1 is None or mask2 is None: return person1_bytes
    
    p1_bgra = cv2.merge([p1_img, mask1]); p2_bgra = cv2.merge([p2_img, mask2])

    scale_factor = 0.80
    scaled_h = int(p1_bgra.shape[0] * scale_factor)
    scaled_w = int(p1_bgra.shape[1] * scale_factor)
    
    p1_scaled = cv2.resize(p1_bgra, (scaled_w, scaled_h), interpolation=cv2.INTER_AREA)
    p2_scaled = cv2.resize(p2_bgra, (scaled_w, scaled_h), interpolation=cv2.INTER_AREA)
    
    # Robust positioning based on scaled width
    overlap = int(scaled_w * 0.3)
    pos1_x = (canvas_w // 2) - scaled_w + (overlap // 2)
    pos2_x = (canvas_w // 2) - (overlap // 2)
    pos_y = (canvas_h - scaled_h) // 2

    # Paste the back layer (man) first
    background = _paste_bgra_on_bgr(p2_scaled, background, pos2_x, pos_y)
    # Paste the front layer (woman) on top
    background = _paste_bgra_on_bgr(p1_scaled, background, pos1_x, pos_y)

    logger.info("Final Alpha Composite image created successfully.")
    return convert_bgr_to_jpeg_bytes(background)

# ------------------------------
# End-to-end Pipeline
# ------------------------------
def preprocess_image(image_bytes: bytes) -> Optional[ProcessedImageOutput]:
    logger.info("Starting robust multi-crop image preprocessing pipeline...")
    img_bgr = load_image_bgr_from_bytes(image_bytes)
    if img_bgr is None: return None
    try:
        landmarks = detect_face_landmarks(img_bgr)
        headshot = convert_bgr_to_jpeg_bytes(align_and_crop_robust(img_bgr, landmarks, crop_mode="headshot"))
        portrait = convert_bgr_to_jpeg_bytes(align_and_crop_robust(img_bgr, landmarks, crop_mode="portrait"))
        half_body = convert_bgr_to_jpeg_bytes(align_and_crop_robust(img_bgr, landmarks, crop_mode="half_body"))
        return ProcessedImageOutput(headshot=headshot, portrait=portrait, half_body=half_body)
    except Exception:
        logger.exception("Preprocessing pipeline failed."); return None
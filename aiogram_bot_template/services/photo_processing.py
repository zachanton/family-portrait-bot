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

def create_composite_image(person1_bytes: bytes, person2_bytes: bytes) -> bytes:
    """
    Creates a simple side-by-side image by concatenating two full portraits.
    """
    logger.info("Starting FINAL SIMPLE CONCATENATION...")
    p1_img, p2_img = load_image_bgr_from_bytes(person1_bytes), load_image_bgr_from_bytes(person2_bytes)
    if p1_img is None or p2_img is None:
        return person1_bytes or person2_bytes

    # Просто соединяем два изображения 1024x1024 по горизонтали
    final_image = cv2.hconcat([p1_img, p2_img])

    logger.info("Final Simple Concatenation created successfully.")
    return convert_bgr_to_jpeg_bytes(final_image)

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
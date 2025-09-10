# aiogram_bot_template/services/photo_processing.py
import cv2
import io
import mediapipe as mp
import numpy as np
import structlog
from typing import Optional, Dict, Any, Tuple
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
RIGHT_EYE_OUTER = 33
LEFT_EYE_OUTER = 263
CHIN_BOTTOM = 152
FOREHEAD_TOP = 10 

CROP_PARAMS = {
    "headshot":  (0.65, 0.15),
    "portrait":  (0.50, 0.20),
    "half_body": (0.35, 0.18),
}

# ------------------------------
# I/O and Image Conversion
# ------------------------------

def load_image_bgr_from_bytes(data: bytes) -> Optional[np.ndarray]:
    """Load image from bytes, auto-rotate from EXIF, and return as BGR uint8."""
    try:
        img = Image.open(io.BytesIO(data))
        img = ImageOps.exif_transpose(img)
        img = img.convert("RGB")
        arr = np.asarray(img)
        return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
    except Exception:
        logger.exception("Failed to load image from bytes")
        return None

def convert_bgr_to_jpeg_bytes(img_bgr: np.ndarray, quality: int = 90) -> bytes:
    """Converts a BGR NumPy array to JPEG bytes."""
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    pil_img = Image.fromarray(img_rgb)
    buffer = io.BytesIO()
    pil_img.save(buffer, format="JPEG", quality=quality, optimize=True)
    return buffer.getvalue()

# ---------------------------------------------
# Face Landmark Detection
# ---------------------------------------------

def detect_face_landmarks(img_bgr: np.ndarray) -> np.ndarray:
    """Detects face landmarks using MediaPipe FaceMesh and returns them in pixel coordinates."""
    h, w = img_bgr.shape[:2]
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    mp_fm = mp.solutions.face_mesh

    with mp_fm.FaceMesh(static_image_mode=True, max_num_faces=1, refine_landmarks=True, min_detection_confidence=0.5) as fm:
        res = fm.process(img_rgb)

    if not res.multi_face_landmarks:
        raise RuntimeError("Face landmarks not found.")
        
    lmk = res.multi_face_landmarks[0].landmark
    return np.array([(p.x * w, p.y * h) for p in lmk], dtype=np.float32)

# --------------------------------------------------------------------
# Aspect Ratio-Preserving Alignment and Cropping
# --------------------------------------------------------------------

def align_and_crop_robust(
    img_bgr: np.ndarray,
    lmk_px: np.ndarray,
    output_size: int = 1024,
    crop_mode: str = "half_body"
) -> np.ndarray:
    """
    Aligns, scales, and crops a face with guaranteed headroom, preserving aspect ratio.
    """
    p_right_eye = lmk_px[RIGHT_EYE_OUTER]
    p_left_eye = lmk_px[LEFT_EYE_OUTER]
    p_chin = lmk_px[CHIN_BOTTOM]
    p_forehead = lmk_px[FOREHEAD_TOP]
    
    target_head_height_frac, top_margin_frac = CROP_PARAMS[crop_mode]

    # 1. Calculate Rotation
    eye_delta = p_left_eye - p_right_eye
    angle_deg = np.degrees(np.arctan2(eye_delta[1], eye_delta[0]))
    
    # 2. Calculate Uniform Scale based on head height
    # <<< ИСПРАВЛЕНИЕ: Корректное формирование матрицы для трансформации точек
    # Create a 3x2 matrix of homogeneous coordinates for the two points
    points_h = np.array([
        [p_chin[0], p_forehead[0]],
        [p_chin[1], p_forehead[1]],
        [1.0, 1.0]
    ])
    rot_mat_3x3 = np.vstack([cv2.getRotationMatrix2D((0,0), angle_deg, 1.0), [0, 0, 1]])
    # Apply rotation to find the vertical distance in the rotated coordinate system
    rotated_head_points = np.dot(rot_mat_3x3, points_h)[:2, :] # Get only x,y
    
    current_head_height = abs(rotated_head_points[1, 0] - rotated_head_points[1, 1]) or 1.0
    
    target_head_height = output_size * target_head_height_frac
    scale = target_head_height / current_head_height
    
    # 3. Build the final transformation matrix
    head_center = (p_chin + p_forehead) / 2.0
    M = cv2.getRotationMatrix2D(tuple(head_center), angle_deg, scale)

    # 4. Adjust translation to position the head with a guaranteed top margin
    transformed_forehead = np.dot(M, (p_forehead[0], p_forehead[1], 1))
    target_y = output_size * top_margin_frac
    M[1, 2] += target_y - transformed_forehead[1]
    
    transformed_head_center = np.dot(M, (head_center[0], head_center[1], 1))
    M[0, 2] += (output_size / 2.0) - transformed_head_center[0]
    
    # 5. Apply the final transformation
    return cv2.warpAffine(
        img_bgr, M, (output_size, output_size),
        flags=cv2.INTER_LANCZOS4,
        borderMode=cv2.BORDER_REPLICATE
    )

# ------------------------------
# End-to-end Pipeline
# ------------------------------
def preprocess_image(image_bytes: bytes) -> Optional[ProcessedImageOutput]:
    """
    Full preprocessing pipeline. Detects landmarks once, then generates all three
    crop versions with the robust alignment method.
    """
    logger.info("Starting robust multi-crop image preprocessing pipeline...")

    img_bgr = load_image_bgr_from_bytes(image_bytes)
    if img_bgr is None:
        return None
    
    try:
        landmarks = detect_face_landmarks(img_bgr)
        
        headshot_bgr = align_and_crop_robust(img_bgr, landmarks, crop_mode="headshot")
        portrait_bgr = align_and_crop_robust(img_bgr, landmarks, crop_mode="portrait")
        half_body_bgr = align_and_crop_robust(img_bgr, landmarks, crop_mode="half_body")
        
        output = ProcessedImageOutput(
            headshot=convert_bgr_to_jpeg_bytes(headshot_bgr),
            portrait=convert_bgr_to_jpeg_bytes(portrait_bgr),
            half_body=convert_bgr_to_jpeg_bytes(half_body_bgr),
        )
        
        logger.info("Robust multi-crop preprocessing finished successfully.")
        return output

    except RuntimeError as e:
        logger.error("A critical error occurred during preprocessing.", error=str(e))
        return None
    except Exception:
        logger.exception("An unexpected exception occurred in the preprocessing pipeline.")
        return None
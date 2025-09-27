# aiogram_bot_template/services/similarity_scorer.py
import asyncio
import io
import math
from typing import List, Optional, Tuple

import cv2
import mediapipe as mp
import numpy as np
import structlog
from PIL import Image, ImageOps

logger = structlog.get_logger(__name__)

# --- MediaPipe Initialization ---
mp_face_detection = mp.solutions.face_detection

# Keypoint indices from MediaPipe Face Detection (6 keypoints)
RIGHT_EYE = 0
LEFT_EYE = 1
NOSE_TIP = 2
MOUTH_CENTER = 3
RIGHT_EAR_TRAGION = 4
LEFT_EAR_TRAGION = 5

class PhotoAnalysisResult(Tuple):
    """A type hint for the output of the analysis function."""
    aligned_image_bytes: bytes
    score: float
    file_unique_id: str
    file_id: str

def load_image_bgr_from_bytes(data: bytes) -> Optional[np.ndarray]:
    """Loads an image from bytes into a BGR NumPy array."""
    try:
        img = Image.open(io.BytesIO(data))
        img = ImageOps.exif_transpose(img)
        if img.mode != "RGB":
            img = img.convert("RGB")
        return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    except Exception:
        logger.exception("Failed to load image from bytes.")
        return None

def convert_bgr_to_jpeg_bytes(img_bgr: np.ndarray, quality: int = 95) -> bytes:
    """Converts a BGR NumPy array to JPEG bytes in memory."""
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    buf = io.BytesIO()
    Image.fromarray(img_rgb).save(buf, format="JPEG", quality=quality, optimize=True)
    return buf.getvalue()

def _calculate_rotation_angle(keypoints: np.ndarray) -> float:
    """
    Calculates the rotation angle to make the head upright.
    It intelligently chooses between eye-to-eye or ear-to-nose vector
    based on the visibility of facial features (frontal vs. profile view).

    Args:
        keypoints: A NumPy array of facial keypoints.

    Returns:
        The angle in degrees for counter-clockwise rotation.
    """
    p_right_eye, p_left_eye = keypoints[RIGHT_EYE], keypoints[LEFT_EYE]
    p_nose_tip = keypoints[NOSE_TIP]
    p_right_ear, p_left_ear = keypoints[RIGHT_EAR_TRAGION], keypoints[LEFT_EAR_TRAGION]

    # Check if both eyes are clearly visible and separated, indicating a frontal view
    inter_eye_dist = np.linalg.norm(p_left_eye - p_right_eye)
    # A simple heuristic: if inter-eye distance is very small, it's likely a profile.
    # We use a threshold relative to a hypothetical face width.
    # A more robust check might use ear distances, but this is effective.
    is_frontal_view = inter_eye_dist > 10  # A small pixel threshold

    if is_frontal_view:
        # For frontal views, align the eyes horizontally.
        eye_delta_y = p_left_eye[1] - p_right_eye[1]
        eye_delta_x = p_left_eye[0] - p_right_eye[0]
        angle = math.degrees(math.atan2(eye_delta_y, eye_delta_x))
    else:
        # For profile views, align the ear-to-nose line horizontally.
        # Determine which ear is visible to use for the calculation.
        # This simple check assumes one ear is more 'central' in profile shots.
        if p_left_ear[0] > 0 and p_right_ear[0] > 0: # Check if both ears were detected
             ear_to_use = p_left_ear if p_left_ear[0] < p_right_ear[0] else p_right_ear
        else: # Fallback if one ear is not detected
            ear_to_use = p_left_ear if p_left_ear[0] > 0 else p_right_ear

        ear_delta_y = p_nose_tip[1] - ear_to_use[1]
        ear_delta_x = p_nose_tip[0] - ear_to_use[0]
        angle = math.degrees(math.atan2(ear_delta_y, ear_delta_x))
        
    return angle

def _analyze_and_align_one_photo(
    img_bgr: np.ndarray, file_unique_id: str, file_id: str
) -> Optional[PhotoAnalysisResult]:
    """
    Analyzes a single image for face quality, pose, and alignment.

    - Rejects images with zero or more than one face.
    - Rejects images where the face is likely a back-of-head view.
    - Rotates the image to align the head vertically.
    - Calculates a quality score.

    Returns:
        A PhotoAnalysisResult tuple containing the aligned image bytes and metadata,
        or None if the image is rejected.
    """
    h, w = img_bgr.shape[:2]
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)

    with mp_face_detection.FaceDetection(
        model_selection=1, min_detection_confidence=0.5
    ) as face_detection:
        results = face_detection.process(img_rgb)

        # RULE 1: Must have exactly one face.
        if not results.detections or len(results.detections) != 1:
            return None

        detection = results.detections[0]

        # Extract keypoints
        keypoints_relative = detection.location_data.relative_keypoints
        keypoints = np.array([(kp.x * w, kp.y * h) for kp in keypoints_relative])

        # RULE 2: Filter out back-of-head shots.
        # A simple but effective check is to ensure the core facial features (eyes, nose, mouth) are detected.
        # MediaPipe's 6 keypoints include these, so if they are all present (within image bounds), it's not a back view.
        if not all(0 <= kp.x < 1 and 0 <= kp.y < 1 for kp in keypoints_relative[:4]):
             return None # Missing eye, nose, or mouth center.

        # RULE 3: Rotate image to align head vertically.
        angle = _calculate_rotation_angle(keypoints)
        
        # Calculate the center of the face bounding box for rotation
        box_data = detection.location_data.relative_bounding_box
        center_x = int((box_data.xmin + box_data.width / 2) * w)
        center_y = int((box_data.ymin + box_data.height / 2) * h)

        rotation_matrix = cv2.getRotationMatrix2D((center_x, center_y), angle, 1.0)
        
        # Apply the rotation
        aligned_img_bgr = cv2.warpAffine(img_bgr, rotation_matrix, (w, h), borderMode=cv2.BORDER_REPLICATE)
        aligned_image_bytes = convert_bgr_to_jpeg_bytes(aligned_img_bgr)

        # Scoring (can be simplified or expanded as needed)
        detection_score = detection.score[0]
        face_area = (box_data.width * w * box_data.height * h) / (w * h)
        size_score = min(1.0, face_area / 0.20) # Normalize, assuming 20% of image area is a good size

        final_score = (detection_score * 0.8) + (size_score * 0.2)

        return PhotoAnalysisResult((aligned_image_bytes, final_score, file_unique_id, file_id))


async def select_best_photos(
    photo_inputs: List[Tuple[bytes, str, str]],
) -> Optional[List[Tuple[str, str, bytes]]]:
    """
    Selects the best photos from a list based on face detection quality and alignment.

    The "best" photos are those with exactly one, clear, and visible face (from front to profile).
    It returns ALL photos that meet the criteria, sorted by quality score.
    Each returned photo is aligned to have the head be vertical.

    Args:
        photo_inputs: A list of tuples, each containing (image_bytes, file_unique_id, file_id).

    Returns:
        A list of tuples (file_unique_id, file_id, aligned_image_bytes) for all suitable photos,
        or None if no suitable photos are found.
    """
    if not photo_inputs:
        return None

    MIN_ACCEPTABLE_SCORE = 0.65  # Stricter threshold for a single good face

    analysis_tasks = []
    for image_bytes, unique_id, file_id in photo_inputs:
        img_bgr = load_image_bgr_from_bytes(image_bytes)
        if img_bgr is not None:
            task = asyncio.to_thread(_analyze_and_align_one_photo, img_bgr, unique_id, file_id)
            analysis_tasks.append(task)

    results = await asyncio.gather(*analysis_tasks, return_exceptions=True)

    valid_photos = []
    for analysis_result in results:
        if isinstance(analysis_result, Exception):
            logger.warning("Photo analysis failed for one image", exc_info=analysis_result)
            continue
        
        if analysis_result is None:
            continue

        aligned_bytes, score, unique_id, file_id = analysis_result
        if score >= MIN_ACCEPTABLE_SCORE:
            valid_photos.append({
                "unique_id": unique_id,
                "file_id": file_id,
                "bytes": aligned_bytes,
                "score": score,
            })

    if not valid_photos:
        logger.warning(
            "No suitable photo found among candidates that meets the minimum quality score.",
            threshold=MIN_ACCEPTABLE_SCORE,
        )
        return None

    # Sort by score in descending order
    valid_photos.sort(key=lambda x: x["score"], reverse=True)

    logger.info(
        "Selected best photos after alignment and scoring",
        count=len(valid_photos),
        scores=[p["score"] for p in valid_photos],
    )

    return [(p["unique_id"], p["file_id"], p["bytes"]) for p in valid_photos]
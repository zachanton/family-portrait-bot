# aiogram_bot_template/services/similarity_scorer.py
import asyncio
import itertools
from typing import Optional, Tuple, List, Dict, Any

import cv2
import mediapipe as mp
import numpy as np
import structlog

from aiogram_bot_template.services.photo_processing import load_image_bgr_from_bytes

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


def _analyze_face_quality(
    img_bgr: np.ndarray,
) -> List[Dict[str, Any]]:
    """
    Analyzes an image to find faces and extract their quality properties using MediaPipe.

    Returns:
        A list of dictionaries, each containing properties of a detected face.
    """
    h, w = img_bgr.shape[:2]
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    results_list: List[Dict[str, Any]] = []

    with mp_face_detection.FaceDetection(
        model_selection=1, min_detection_confidence=0.5
    ) as face_detection:
        results = face_detection.process(img_rgb)

        if not results.detections:
            return results_list

        for detection in results.detections:
            # Bounding box
            box_data = detection.location_data.relative_bounding_box
            x1 = int(box_data.xmin * w)
            y1 = int(box_data.ymin * h)
            face_w = int(box_data.width * w)
            face_h = int(box_data.height * h)
            x2, y2 = x1 + face_w, y1 + face_h

            # Keypoints
            keypoints = detection.location_data.relative_keypoints
            kps = np.array([(kp.x * w, kp.y * h) for kp in keypoints])

            # --- Scoring ---
            # 1. Detection score
            detection_score = detection.score[0]

            # 2. Keypoint visibility score
            # All 6 keypoints should be within the image bounds.
            visible_kps = [
                0 <= kp.x < 1 and 0 <= kp.y < 1 for kp in keypoints
            ]
            keypoint_score = sum(visible_kps) / len(visible_kps)
            
            # 3. Face size score (relative to image area)
            face_area = (face_w * face_h) / (w * h)
            size_score = min(1.0, face_area / 0.25) # Normalize, assuming 25% of image area is a good size

            # 4. Sharpness score
            face_roi = img_bgr[max(0, y1):min(h, y2), max(0, x1):min(w, x2)]
            if face_roi.size > 0:
                gray = cv2.cvtColor(face_roi, cv2.COLOR_BGR2GRAY)
                sharpness = cv2.Laplacian(gray, cv2.CV_64F).var()
                sharpness_score = min(1.0, sharpness / 150.0) # Normalize, assuming good photo > 100
            else:
                sharpness_score = 0.0

            # --- Final Score ---
            # Weighted score to prioritize detection and keypoint visibility.
            final_score = (
                (detection_score * 0.4) +
                (keypoint_score * 0.4) +
                (sharpness_score * 0.15) +
                (size_score * 0.05)
            )

            results_list.append({
                "bbox": (x1, y1, x2, y2),
                "keypoints": kps,
                "score": final_score,
            })
            
    return results_list


async def select_best_photos(
    photo_inputs: List[Tuple[bytes, str, str]],
    num_to_select: int = 3,
) -> Optional[List[Tuple[str, str, bytes]]]:
    """
    Selects the best photos from a list based on face detection quality.

    The "best" photos are those with exactly one, clear, and visible face.
    If fewer than `num_to_select` valid photos are found, the best one is duplicated.

    Args:
        photo_inputs: A list of tuples, each containing (image_bytes, file_unique_id, file_id).
        num_to_select: The target number of photos to return.

    Returns:
        A list of tuples (file_unique_id, file_id, image_bytes) for the best photos,
        or None if no suitable photos are found.
    """
    if not photo_inputs:
        return None

    MIN_ACCEPTABLE_SCORE = 0.60  # Stricter threshold for a single good face

    analysis_tasks = []
    for image_bytes, unique_id, file_id in photo_inputs:
        img_bgr = load_image_bgr_from_bytes(image_bytes)
        if img_bgr is not None:
            task = asyncio.to_thread(_analyze_face_quality, img_bgr)
            analysis_tasks.append((task, unique_id, file_id, image_bytes))

    results = await asyncio.gather(*(task for task, _, _, _ in analysis_tasks), return_exceptions=True)

    valid_photos = []
    for i, face_result in enumerate(results):
        _, unique_id, file_id, image_bytes = analysis_tasks[i]

        if isinstance(face_result, Exception):
            logger.warning("Photo analysis failed for one image", exc_info=face_result, file_unique_id=unique_id)
            continue

        # Rule: Must have exactly one face
        if len(face_result) != 1:
            continue

        face = face_result[0]
        score = face["score"]

        if score >= MIN_ACCEPTABLE_SCORE:
            valid_photos.append({
                "unique_id": unique_id,
                "file_id": file_id,
                "bytes": image_bytes,
                "score": score,
            })

    if not valid_photos:
        logger.warning(
            "No suitable photo found among candidates that meets the minimum quality score.",
            threshold=MIN_ACCEPTABLE_SCORE
        )
        return None

    # Sort by score in descending order
    valid_photos.sort(key=lambda x: x["score"], reverse=True)

    # Get the top N photos
    top_photos = valid_photos[:num_to_select]

    # If we have fewer than N, duplicate the best one to fill the list
    if 0 < len(top_photos) < num_to_select:
        best_photo = top_photos[0]
        num_needed = num_to_select - len(top_photos)
        top_photos.extend([best_photo] * num_needed)
    
    logger.info("Selected best photos", count=len(top_photos), scores=[p['score'] for p in top_photos])

    return [
        (p["unique_id"], p["file_id"], p["bytes"]) for p in top_photos
    ]
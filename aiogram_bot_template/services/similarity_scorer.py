# aiogram_bot_template/services/similarity_scorer.py
import asyncio
import io
import math
from typing import Any, Dict, List, Optional, Tuple

import cv2
import mediapipe as mp
import numpy as np
import structlog
from PIL import Image, ImageOps


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
    Includes a geometric check to filter out occluded or distorted faces.

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
            visible_kps = [0 <= kp.x < 1 and 0 <= kp.y < 1 for kp in keypoints]
            keypoint_score = sum(visible_kps) / len(visible_kps)

            # 3. Geometric consistency score (for occlusion/distortion)
            # This score checks if facial features are in expected positions relative to each other.
            # It helps reject images with significant occlusions (e.g., hand over mouth) or distortions.
            try:
                p_right_eye, p_left_eye = kps[RIGHT_EYE], kps[LEFT_EYE]
                p_nose_tip = kps[NOSE_TIP]
                p_mouth_center = kps[MOUTH_CENTER]

                # Use inter-eye distance as a scale-invariant unit of measurement.
                inter_eye_dist = np.linalg.norm(p_left_eye - p_right_eye)
                if inter_eye_dist < 1e-6:  # Avoid division by zero
                    raise ZeroDivisionError

                eyes_center = (p_left_eye + p_right_eye) / 2.0

                # Check 1: Horizontal alignment of nose and mouth relative to eyes' center.
                # A large horizontal deviation suggests a severe head tilt or occlusion.
                eye_vector = p_left_eye - p_right_eye
                nose_projection_offset = abs(np.dot(p_nose_tip - eyes_center, eye_vector) / (inter_eye_dist**2))
                mouth_projection_offset = abs(np.dot(p_mouth_center - eyes_center, eye_vector) / (inter_eye_dist**2))
                
                # Normalize error: score is 1.0 for perfect alignment, 0.0 for high deviation.
                alignment_error = nose_projection_offset + mouth_projection_offset
                alignment_score = max(0.0, 1.0 - (alignment_error / 0.7))

                # Check 2: Vertical distance ratio between nose and mouth.
                # An object (like a hotdog) can push the mouth landmark, altering this ratio.
                nose_mouth_dist = np.linalg.norm(p_nose_tip - p_mouth_center)
                ratio = nose_mouth_dist / inter_eye_dist
                
                # Use a Gaussian-like function to score the ratio. Ideal is ~1.0.
                ratio_score = math.exp(-(((ratio - 1.0) ** 2) / (2 * 0.2**2)))

                geometric_consistency_score = (alignment_score * 0.5) + (ratio_score * 0.5)
            except (ZeroDivisionError, IndexError):
                geometric_consistency_score = 0.0

            # 4. Face size score (relative to image area)
            face_area = (face_w * face_h) / (w * h)
            size_score = min(
                1.0, face_area / 0.25
            )  # Normalize, assuming 25% of image area is a good size

            # 5. Sharpness score
            face_roi = img_bgr[max(0, y1) : min(h, y2), max(0, x1) : min(w, x2)]
            if face_roi.size > 0:
                gray = cv2.cvtColor(face_roi, cv2.COLOR_BGR2GRAY)
                sharpness = cv2.Laplacian(gray, cv2.CV_64F).var()
                sharpness_score = min(
                    1.0, sharpness / 150.0
                )  # Normalize, assuming good photo > 100
            else:
                sharpness_score = 0.0

            # --- Final Score (UPDATED with occlusion check) ---
            final_score = (
                (detection_score * 0.25)
                + (keypoint_score * 0.30)
                + (geometric_consistency_score * 0.30)  # Added new score
                + (sharpness_score * 0.10)
                + (size_score * 0.05)
            )

            results_list.append(
                {
                    "bbox": (x1, y1, x2, y2),
                    "keypoints": kps,
                    "score": final_score,
                }
            )

    return results_list


async def select_best_photos(
    photo_inputs: List[Tuple[bytes, str, str]],
) -> Optional[List[Tuple[str, str, bytes]]]:
    """
    Selects the best photos from a list based on face detection quality.

    The "best" photos are those with exactly one, clear, and visible face.
    It returns ALL photos that meet the criteria, sorted by quality score.

    Args:
        photo_inputs: A list of tuples, each containing (image_bytes, file_unique_id, file_id).

    Returns:
        A list of tuples (file_unique_id, file_id, image_bytes) for all suitable photos,
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

    results = await asyncio.gather(
        *(task for task, _, _, _ in analysis_tasks), return_exceptions=True
    )

    valid_photos = []
    for i, face_result in enumerate(results):
        _, unique_id, file_id, image_bytes = analysis_tasks[i]

        if isinstance(face_result, Exception):
            logger.warning(
                "Photo analysis failed for one image",
                exc_info=face_result,
                file_unique_id=unique_id,
            )
            continue

        # Rule: Must have exactly one face
        if len(face_result) != 1:
            continue

        face = face_result[0]
        score = face["score"]

        if score >= MIN_ACCEPTABLE_SCORE:
            valid_photos.append(
                {
                    "unique_id": unique_id,
                    "file_id": file_id,
                    "bytes": image_bytes,
                    "score": score,
                }
            )

    if not valid_photos:
        logger.warning(
            "No suitable photo found among candidates that meets the minimum quality score.",
            threshold=MIN_ACCEPTABLE_SCORE,
        )
        return None

    # Sort by score in descending order
    valid_photos.sort(key=lambda x: x["score"], reverse=True)

    logger.info(
        "Selected best photos",
        count=len(valid_photos),
        scores=[p["score"] for p in valid_photos],
    )

    return [(p["unique_id"], p["file_id"], p["bytes"]) for p in valid_photos]
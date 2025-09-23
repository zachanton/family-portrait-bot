# aiogram_bot_template/services/similarity_scorer.py
import asyncio
import threading
from typing import Optional, Tuple, List, Dict, Any

import cv2
import numpy as np
import structlog

# Replace DeepFace with InsightFace
# pip install insightface onnxruntime   # or torch/torchvision if you prefer PyTorch runtime
from insightface.app import FaceAnalysis

from aiogram_bot_template.services.photo_processing import (
    load_image_bgr_from_bytes,
    convert_bgr_to_jpeg_bytes,
)

logger = structlog.get_logger(__name__)

# ----------------------- InsightFace runtime -----------------------
# 'buffalo_l' uses a strong ArcFace-based recognizer and RetinaFace-like detector
# Works on CPU with onnxruntime or on GPU if available.
_INSIGHT_APP: Optional[FaceAnalysis] = None
# A lock to ensure thread-safe initialization of the FaceAnalysis app
_INSIGHT_APP_LOCK = threading.Lock()


def _get_app() -> FaceAnalysis:
    """
    Safely initializes and returns the FaceAnalysis application instance.
    Uses a lock to prevent race conditions during initialization.
    """
    global _INSIGHT_APP
    # First, check if the app is already initialized without locking for performance.
    if _INSIGHT_APP is None:
        # If not initialized, acquire the lock.
        with _INSIGHT_APP_LOCK:
            # Double-check inside the lock to see if another thread initialized it
            # while this thread was waiting for the lock.
            if _INSIGHT_APP is None:
                logger.info("Initializing InsightFace model for the first time...")
                # ctx_id = -1 -> CPU; set 0 for first GPU if you use GPU
                _INSIGHT_APP = FaceAnalysis(name="buffalo_l", allowed_modules=['detection', 'recognition', 'pose'])
                _INSIGHT_APP.prepare(ctx_id=-1, det_size=(640, 640))
                logger.info("InsightFace model initialized successfully.")
    return _INSIGHT_APP


# ----------------------- Analysis & Scoring Helpers -----------------------

def _cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    # Both vectors are expected L2-normalized; safe-guard anyway.
    a = a / (np.linalg.norm(a) + 1e-12)
    b = b / (np.linalg.norm(b) + 1e-12)
    return float(np.dot(a, b))


def _calculate_blurriness(image_bgr: np.ndarray, bbox: Tuple[int, int, int, int]) -> float:
    """
    Calculates a sharpness score for a face region using the variance of the Laplacian.
    Higher values mean a sharper image.
    """
    x1, y1, x2, y2 = bbox
    face_roi = image_bgr[y1:y2, x1:x2]
    if face_roi.size == 0:
        return 0.0
    gray = cv2.cvtColor(face_roi, cv2.COLOR_BGR2GRAY)
    variance = cv2.Laplacian(gray, cv2.CV_64F).var()
    # Normalize score to a 0-1 range, assuming a good photo is > 100
    return min(1.0, variance / 150.0)


def _analyze_faces(
    img_bgr: np.ndarray,
    min_det_score: float = 0.5,
    min_size: int = 64,
) -> List[Dict[str, Any]]:
    """
    Analyzes an image to find faces and extract their properties.

    Returns:
        A list of dictionaries, each containing properties of a detected face.
    """
    app = _get_app()
    faces = app.get(img_bgr)
    results: List[Dict[str, Any]] = []
    h, w = img_bgr.shape[:2]

    for f in faces:
        x1, y1, x2, y2 = map(int, f.bbox.astype(int))
        face_w = max(0, min(w, x2) - max(0, x1))
        face_h = max(0, min(h, y2) - max(0, y1))

        if getattr(f, "det_score", 1.0) < min_det_score or min(face_w, face_h) < min_size:
            continue

        normed = getattr(f, "normed_embedding", None)
        if normed is None:
            emb = np.asarray(f.embedding, dtype=np.float32)
            normed = emb / (np.linalg.norm(emb) + 1e-12)
        else:
            normed = np.asarray(normed, dtype=np.float32)

        results.append({
            "bbox": (x1, y1, x2, y2),
            "score": float(getattr(f, "det_score", 1.0)),
            "embedding": np.asarray(getattr(f, "embedding", normed), dtype=np.float32),
            "normed": normed,
            "pose": tuple(f.pose.astype(float)) if hasattr(f, 'pose') and f.pose is not None else (0.0, 0.0, 0.0),
            "size": (face_w, face_h),
            "kps": f.kps.astype(int) if hasattr(f, 'kps') and f.kps is not None else None,
        })
    return results


async def select_best_photo(
    photo_inputs: List[Tuple[bytes, str, str]]
) -> Optional[Tuple[str, str, bytes]]:
    """
    Selects the best photo from a list based on a composite quality score.

    The "best" photo is one with exactly one, clear, frontal, sharp face,
    and without significant occlusions or unnatural expressions.

    Args:
        photo_inputs: A list of tuples, each containing (image_bytes, file_unique_id, file_id).

    Returns:
        A tuple of (file_unique_id, file_id, image_bytes) for the best photo,
        or None if no photo meets the minimum quality threshold.
    """
    if not photo_inputs:
        return None

    MIN_ACCEPTABLE_SCORE = 0.70  # Stricter threshold

    best_photo_info = None
    highest_score = -1.0

    analysis_tasks = []
    for image_bytes, unique_id, file_id in photo_inputs:
        img_bgr = load_image_bgr_from_bytes(image_bytes)
        if img_bgr is not None:
            task = asyncio.to_thread(_analyze_faces, img_bgr)
            analysis_tasks.append((task, unique_id, file_id, image_bytes, img_bgr))

    results = await asyncio.gather(*(task for task, _, _, _, _ in analysis_tasks), return_exceptions=True)

    for i, face_result in enumerate(results):
        _, unique_id, file_id, image_bytes, img_bgr = analysis_tasks[i]
        img_h, img_w, _ = img_bgr.shape

        if isinstance(face_result, Exception):
            logger.warning("Photo analysis failed for one image", exc_info=face_result, file_unique_id=unique_id)
            continue

        if len(face_result) != 1:
            continue

        face = face_result[0]

        # --- Scoring criteria ---
        # 1. Landmark Sanity Score (NEW): Critical check for occlusions and extreme expressions.
        landmark_score = 0.0
        if face['kps'] is not None and len(face['kps']) == 5:
            kps = face['kps']
            nose_y = kps[2][1]
            mouth_y = (kps[3][1] + kps[4][1]) / 2
            eye_y = (kps[0][1] + kps[1][1]) / 2
            
            # Sanity check: mouth must be below the nose.
            if mouth_y > nose_y:
                # Sanity check 2: vertical distance between mouth and nose should be reasonable.
                eye_nose_dist = abs(nose_y - eye_y)
                nose_mouth_dist = abs(mouth_y - nose_y)
                # A natural face has a smaller nose-mouth distance than eye-nose distance.
                if eye_nose_dist > 0 and (nose_mouth_dist / eye_nose_dist) < 1.5:
                     landmark_score = 1.0

        # 2. Detection Confidence
        detection_confidence = face['score']
        
        # 3. Pose Score
        pitch, yaw, roll = face['pose']
        pose_deviation = abs(yaw) + abs(pitch) * 0.5 + abs(roll) * 0.25
        pose_score = max(0, 1.0 - pose_deviation / 45.0)

        # 4. Sharpness Score
        blur_score = _calculate_blurriness(img_bgr, face['bbox'])
        
        # --- Final weighted score ---
        # Landmark score is now the most important factor.
        final_score = (
            (landmark_score * 0.4) +           # Heavily penalizes bad landmarks (occlusion).
            (detection_confidence * 0.3) +
            (pose_score * 0.2) +
            (blur_score * 0.1)
        )

        if final_score > highest_score:
            highest_score = final_score
            best_photo_info = (unique_id, file_id, image_bytes)

    if best_photo_info and highest_score >= MIN_ACCEPTABLE_SCORE:
        logger.info("Selected best photo", file_unique_id=best_photo_info[0], score=highest_score)
        return best_photo_info
    else:
        logger.warning(
            "No suitable photo found among candidates that meets the minimum quality score.",
            best_score=highest_score,
            threshold=MIN_ACCEPTABLE_SCORE
        )
        return None


# ----------------------- Public API -----------------------

async def get_face_similarity_score(
    single_image_bytes: bytes,
    pair_image_bytes: bytes,
) -> Optional[float]:
    """
    Computes similarity between the person in a single-portrait and the best-matching person
    in a two-person (pair) portrait. Returns a cosine similarity in [ -1.0 ; 1.0 ].
    """
    if not single_image_bytes or not pair_image_bytes:
        return None

    try:
        img1 = load_image_bgr_from_bytes(single_image_bytes)
        img2 = load_image_bgr_from_bytes(pair_image_bytes)
        if img1 is None or img2 is None:
            logger.error("Could not decode one or both images from bytes.")
            return None

        single_faces, pair_faces = await asyncio.gather(
            asyncio.to_thread(_analyze_faces, img1),
            asyncio.to_thread(_analyze_faces, img2),
        )

        if not single_faces:
            logger.warning("No face detected in single portrait.")
            return None
        if not pair_faces:
            logger.warning("No faces detected in pair portrait.")
            return None

        single = max(single_faces, key=lambda d: d["score"])
        s_vec = single["normed"]
        
        best = -1.0
        for p in pair_faces:
            sim = _cosine_sim(s_vec, p["normed"])
            if sim > best:
                best = sim

        return float(best)

    except Exception:
        logger.exception("Unexpected error in get_face_similarity_score.")
        return None


def crop_generated_image(
    image_bytes: bytes,
) -> Tuple[Optional[bytes], Optional[bytes]]:
    """
    (unchanged) Splits a side-by-side image into left/right halves and returns JPEG bytes.
    """
    try:
        img_np = load_image_bgr_from_bytes(image_bytes)
        if img_np is None:
            return None, None
        height, width, _ = img_np.shape
        midpoint = width // 2
        left_half_bgr = img_np[:, :midpoint]
        right_half_bgr = img_np[:, midpoint:]
        return (
            convert_bgr_to_jpeg_bytes(left_half_bgr),
            convert_bgr_to_jpeg_bytes(right_half_bgr),
        )
    except Exception:
        logger.exception("Failed to crop the generated image.")
        return None, None
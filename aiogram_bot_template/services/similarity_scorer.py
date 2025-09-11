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
                _INSIGHT_APP = FaceAnalysis(name="buffalo_l")
                _INSIGHT_APP.prepare(ctx_id=-1, det_size=(640, 640))
                logger.info("InsightFace model initialized successfully.")
    return _INSIGHT_APP


# ----------------------- Embedding helpers -----------------------

def _cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    # Both vectors are expected L2-normalized; safe-guard anyway.
    a = a / (np.linalg.norm(a) + 1e-12)
    b = b / (np.linalg.norm(b) + 1e-12)
    return float(np.dot(a, b))


def _extract_faces_and_embeddings(
    img_bgr: np.ndarray,
    min_det_score: float = 0.5,
    min_size: int = 64,
) -> List[Dict[str, Any]]:
    """
    Returns a list of dicts: { 'bbox': (x1,y1,x2,y2), 'score': float, 'embedding': np.ndarray, 'normed': np.ndarray }
    Filters out low-quality detections by score and face size.
    """
    app = _get_app()
    faces = app.get(
        img_bgr
    )  # returns list of Face objects with bbox, kps, embedding, normed_embedding
    results: List[Dict[str, Any]] = []

    h, w = img_bgr.shape[:2]
    for f in faces:
        x1, y1, x2, y2 = map(int, f.bbox.astype(int))
        # basic size/score filters to avoid tiny/background faces
        face_w = max(0, min(w, x2) - max(0, x1))
        face_h = max(0, min(h, y2) - max(0, y1))
        if getattr(f, "det_score", getattr(f, "score", 1.0)) < min_det_score:
            continue
        if min(face_w, face_h) < min_size:
            continue

        # InsightFace exposes both embedding and normed_embedding; for cosine use normalized vectors
        normed = getattr(f, "normed_embedding", None)
        if normed is None:
            emb = np.asarray(f.embedding, dtype=np.float32)
            normed = emb / (np.linalg.norm(emb) + 1e-12)
        else:
            normed = np.asarray(normed, dtype=np.float32)

        results.append(
            {
                "bbox": (x1, y1, x2, y2),
                "score": float(getattr(f, "det_score", getattr(f, "score", 1.0))),
                "embedding": np.asarray(getattr(f, "embedding", normed), dtype=np.float32),
                "normed": normed,
            }
        )
    return results


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

        # Heavy ops off the event loop
        single_faces, pair_faces = await asyncio.gather(
            asyncio.to_thread(_extract_faces_and_embeddings, img1),
            asyncio.to_thread(_extract_faces_and_embeddings, img2),
        )

        if not single_faces:
            logger.warning("No face detected in single portrait.")
            return None
        if not pair_faces:
            logger.warning("No faces detected in pair portrait.")
            return None

        # Use the most confident face from the single portrait
        single = max(single_faces, key=lambda d: d["score"])
        s_vec = single["normed"]

        # Compare with all faces in the pair; take the best cosine similarity
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
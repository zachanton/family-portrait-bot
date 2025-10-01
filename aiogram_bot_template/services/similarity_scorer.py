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

# NEW: Import insightface for advanced identity analysis
from insightface.app import FaceAnalysis

logger = structlog.get_logger(__name__)

# --- MediaPipe Initialization ---
mp_face_detection = mp.solutions.face_detection
mp_selfie_seg = mp.solutions.selfie_segmentation

# --- NEW: InsightFace Singleton Initialization ---
_face_analysis_app: Optional[FaceAnalysis] = None

def _get_face_analysis_app() -> FaceAnalysis:
    """
    Initializes and returns a singleton FaceAnalysis instance.
    This ensures the model is loaded into memory only once.
    """
    global _face_analysis_app
    if _face_analysis_app is None:
        logger.info("Initializing InsightFace model for the first time...")
        # Force CPU provider to avoid accidental GPU requirement.
        app = FaceAnalysis(name="buffalo_l", providers=['CPUExecutionProvider'])
        app.prepare(ctx_id=0, det_size=(640, 640))
        _face_analysis_app = app
        logger.info("InsightFace model initialized successfully.")
    return _face_analysis_app

# --- NEW: Processing constants ---
# The standard size for each tile in the final collage
STANDARD_TILE_WIDTH = 576
STANDARD_TILE_HEIGHT = 512
# A photo will be rejected if the detected face area is less than this percentage of the total image area.
# This prevents extreme upscaling of low-quality images.
MIN_FACE_AREA_RATIO = 0.05  # 5% of the image

# Keypoint indices from MediaPipe Face Detection (6 keypoints)
RIGHT_EYE = 0
LEFT_EYE = 1
NOSE_TIP = 2
MOUTH_CENTER = 3
RIGHT_EAR_TRAGION = 4
LEFT_EAR_TRAGION = 5


class PhotoAnalysisResult(Tuple):
    """A type hint for the output of the analysis and processing function."""
    processed_image_bytes: bytes
    score: float
    file_unique_id: str
    file_id: str


# --- I/O Functions (unchanged) ---
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


# --- Image Processing Helpers (Moved from photo_processing.py) ---

def _srgb_to_linear_01(bgr_u8: np.ndarray) -> np.ndarray:
    x = bgr_u8.astype(np.float32) / 255.0
    a = 0.055
    low = x <= 0.04045
    out = np.empty_like(x)
    out[low]  = x[low] / 12.92
    out[~low] = ((x[~low] + a) / (1 + a)) ** 2.4
    return out

def _linear_to_srgb_u8(lin: np.ndarray) -> np.ndarray:
    x = np.clip(lin, 0.0, 1.0)
    a = 0.055
    low = x <= 0.0031308
    out = np.empty_like(x)
    out[low]  = x[low] * 12.92
    out[~low] = (1 + a) * (x[~low] ** (1/2.4)) - a
    return np.clip(out * 255.0 + 0.5, 0, 255).astype(np.uint8)

def _shades_of_gray_cc_linear(bgr: np.ndarray, p: int = 4, gain_clip=(0.90, 1.10)) -> np.ndarray:
    lin = _srgb_to_linear_01(bgr)
    m = np.power(np.mean(np.power(lin, p), axis=(0, 1)) + 1e-8, 1.0 / p)
    g = float(np.mean(m))
    gains = g / (m + 1e-8)
    if (np.max(gains) - np.min(gains)) < 0.06:
        return bgr.copy()
    gains = np.clip(gains, gain_clip[0], gain_clip[1])
    return _linear_to_srgb_u8(lin * gains[None, None, :])

def _clahe_conditional(bgr: np.ndarray, clip_limit: float = 1.05, tile=(8, 8), std_thresh: float = 45.0) -> np.ndarray:
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    if float(l.std()) < std_thresh:
        clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile)
        l = clahe.apply(l)
    return cv2.cvtColor(cv2.merge((l, a, b)), cv2.COLOR_LAB2BGR)

def _center_crop_to_aspect(bgr: np.ndarray, aspect: float) -> np.ndarray:
    h, w = bgr.shape[:2]
    ar = w / float(h)
    if ar > aspect:
        new_w = int(round(h * aspect))
        x1 = max(0, (w - new_w) // 2)
        return bgr[:, x1:x1 + new_w]
    else:
        new_h = int(round(w / aspect))
        y1 = max(0, (h - new_h) // 2 - int(0.05 * h))
        y1 = max(0, min(y1, h - new_h))
        return bgr[y1:y1 + new_h, :]

def _crop_around_face(bgr: np.ndarray, aspect: float, detection) -> np.ndarray:
    h, w = bgr.shape[:2]
    r = detection.location_data.relative_bounding_box
    xa = max(0.0, r.xmin) * w
    ya = max(0.0, r.ymin) * h
    bw = max(1.0, r.width * w)
    bh = max(1.0, r.height * h)
    
    cx, cy = xa + bw / 2.0, ya + bh / 2.0
    s = max(bw, bh) * 2.4
    tw, th = s, s / aspect
    scale = min(w / max(tw, 1e-6), h / max(th, 1e-6), 1.0)
    tw *= scale; th *= scale
    left = int(round(cx - tw / 2.0)); top = int(round(cy - th / 2.0))
    left = max(0, min(left, w - int(tw))); top = max(0, min(top, h - int(th)))
    right = left + int(tw); bottom = top + int(th)
    return bgr[top:bottom, left:right]

def _resize_smart(bgr: np.ndarray, W: int, H: int) -> np.ndarray:
    h, w = bgr.shape[:2]
    interp = cv2.INTER_AREA if (w > W or h > H) else cv2.INTER_CUBIC
    return cv2.resize(bgr, (W, H), interpolation=interp)

def _person_alpha_mask_improved(bgr: np.ndarray, t_fg=0.92, t_bg=0.18, feather_px=6) -> np.ndarray:
    h, w = bgr.shape[:2]
    with mp_selfie_seg.SelfieSegmentation(model_selection=1) as seg:
        res = seg.process(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
    if res is None or res.segmentation_mask is None:
        return np.ones((h, w), dtype=np.float32)
    prob = res.segmentation_mask.astype(np.float32)
    sure_fg = (prob >= t_fg).astype(np.uint8) * 255
    sure_bg = (prob <= t_bg).astype(np.uint8) * 255
    kernel = np.ones((5, 5), np.uint8)
    sure_fg = cv2.morphologyEx(sure_fg, cv2.MORPH_CLOSE, kernel, iterations=1)
    sure_bg = cv2.morphologyEx(sure_bg, cv2.MORPH_CLOSE, kernel, iterations=1)
    dist_fg = cv2.distanceTransform(cv2.bitwise_not(sure_fg), cv2.DIST_L2, 3)
    dist_bg = cv2.distanceTransform(cv2.bitwise_not(sure_bg), cv2.DIST_L2, 3)
    eps = 1e-6
    a_unknown = dist_bg / (dist_bg + dist_fg + eps)
    a_unknown = np.clip(a_unknown, 0.0, 1.0)
    alpha = np.where(sure_fg == 255, 1.0, np.where(sure_bg == 255, 0.0, a_unknown)).astype(np.float32)
    alpha_bi = cv2.bilateralFilter(alpha, d=7, sigmaColor=0.15, sigmaSpace=5)
    return cv2.GaussianBlur(alpha_bi, (0, 0), sigmaX=max(3, feather_px)/3.0, sigmaY=max(3, feather_px)/3.0)

def _composite_on_gray_improved(bgr: np.ndarray, bg=(190, 190, 190)) -> np.ndarray:
    a = _person_alpha_mask_improved(bgr)[:, :, None]
    bg_img = np.full_like(bgr, bg, dtype=np.uint8)
    return (a * bgr.astype(np.float32) + (1.0 - a) * bg_img.astype(np.float32)).astype(np.uint8)

def _usm(bgr: np.ndarray, amount: float = 0.45, radius: float = 0.7, thresh: int = 3) -> np.ndarray:
    blur = cv2.GaussianBlur(bgr, (0, 0), radius)
    mask = cv2.subtract(bgr, blur)
    gray = cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY)
    mask[gray < thresh] = 0
    return cv2.addWeighted(bgr, 1.0, mask, amount, 0)

# --- Core Logic ---

def _calculate_rotation_angle(keypoints: np.ndarray) -> float:
    """Calculates the rotation angle to make the head upright."""
    p_right_eye, p_left_eye = keypoints[RIGHT_EYE], keypoints[LEFT_EYE]
    eye_delta_y = p_left_eye[1] - p_right_eye[1]
    eye_delta_x = p_left_eye[0] - p_right_eye[0]
    return math.degrees(math.atan2(eye_delta_y, eye_delta_x))

def _analyze_and_process_one_photo(
    img_bgr: np.ndarray, file_unique_id: str, file_id: str
) -> Optional[PhotoAnalysisResult]:
    """
    Analyzes a single image for face quality and fully preprocesses it into a
    standardized tile for collage creation.

    This function performs the entire single-image pipeline:
    - Rejects images with zero or more than one face.
    - Rejects images where the face is too small.
    - Rotates the image to align the head vertically.
    - Applies color correction and light contrast enhancement.
    - Crops around the face to a standard aspect ratio.
    - Resizes to a standard tile size.
    - Removes the background and composites onto a neutral gray.
    - Applies a light sharpening filter.
    - Calculates a quality score.

    Returns:
        A PhotoAnalysisResult tuple containing the processed image bytes and metadata,
        or None if the image is rejected.
    """
    h, w = img_bgr.shape[:2]
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)

    with mp_face_detection.FaceDetection(
        model_selection=1, min_detection_confidence=0.5
    ) as face_detection:
        results = face_detection.process(img_rgb)

        if not results.detections or len(results.detections) != 1:
            return None # RULE 1: Must have exactly one face.
        
        detection = results.detections[0]
        box_data = detection.location_data.relative_bounding_box
        
        # RULE 2: Face must be a minimum size relative to the image.
        face_area_ratio = box_data.width * box_data.height
        if face_area_ratio < MIN_FACE_AREA_RATIO:
            logger.debug("Rejected image: face too small", ratio=face_area_ratio)
            return None

        # --- Start Processing Pipeline ---
        # 1. Rotate image to align head vertically.
        keypoints_relative = detection.location_data.relative_keypoints
        keypoints = np.array([(kp.x * w, kp.y * h) for kp in keypoints_relative])
        angle = _calculate_rotation_angle(keypoints)
        center_x = int((box_data.xmin + box_data.width / 2) * w)
        center_y = int((box_data.ymin + box_data.height / 2) * h)
        rotation_matrix = cv2.getRotationMatrix2D((center_x, center_y), angle, 1.0)
        aligned_img_bgr = cv2.warpAffine(img_bgr, rotation_matrix, (w, h), borderMode=cv2.BORDER_REPLICATE)
        
        # 2. Apply color and contrast enhancements
        processed_img = _shades_of_gray_cc_linear(aligned_img_bgr)
        processed_img = _clahe_conditional(processed_img)

        # 3. Crop around the face to the standard tile aspect ratio
        target_aspect = STANDARD_TILE_WIDTH / STANDARD_TILE_HEIGHT
        processed_img = _crop_around_face(processed_img, target_aspect, detection)

        # 4. Resize to standard tile dimensions
        processed_img = _resize_smart(processed_img, STANDARD_TILE_WIDTH, STANDARD_TILE_HEIGHT)

        # 5. Remove background and composite on neutral gray
        processed_img = _composite_on_gray_improved(processed_img)
        
        # 6. Apply light Unsharp Mask to recover texture
        processed_img = _usm(processed_img)

        processed_image_bytes = convert_bgr_to_jpeg_bytes(processed_img)

        # Scoring
        detection_score = detection.score[0]
        size_score = min(1.0, face_area_ratio / 0.20)
        final_score = (detection_score * 0.8) + (size_score * 0.2)

        return PhotoAnalysisResult((processed_image_bytes, final_score, file_unique_id, file_id))


async def select_best_photos_and_process(
    photo_inputs: List[Tuple[bytes, str, str]],
) -> Optional[List[Tuple[str, str, bytes]]]:
    """
    Selects the best photos from a list, processes them into standardized tiles,
    and returns the results.

    The "best" photos are those with exactly one, clear, and sufficiently large face.
    It returns ALL photos that meet the criteria, sorted by quality score.
    Each returned photo is a fully processed 576x512 tile ready for collage assembly.

    Args:
        photo_inputs: A list of tuples, each containing (image_bytes, file_unique_id, file_id).

    Returns:
        A list of tuples (file_unique_id, file_id, processed_image_bytes) for all suitable photos,
        or None if no suitable photos are found.
    """
    if not photo_inputs:
        return None

    MIN_ACCEPTABLE_SCORE = 0.65

    analysis_tasks = []
    for image_bytes, unique_id, file_id in photo_inputs:
        img_bgr = load_image_bgr_from_bytes(image_bytes)
        if img_bgr is not None:
            task = asyncio.to_thread(_analyze_and_process_one_photo, img_bgr, unique_id, file_id)
            analysis_tasks.append(task)

    results = await asyncio.gather(*analysis_tasks, return_exceptions=True)

    valid_photos = []
    for res in results:
        if isinstance(res, Exception):
            logger.warning("Photo processing failed for one image", exc_info=res)
            continue
        if res is None:
            continue

        processed_bytes, score, unique_id, file_id = res
        if score >= MIN_ACCEPTABLE_SCORE:
            valid_photos.append({
                "unique_id": unique_id, "file_id": file_id, "bytes": processed_bytes, "score": score,
            })

    if not valid_photos:
        logger.warning(
            "No suitable photo found among candidates that meets the minimum quality score.",
            threshold=MIN_ACCEPTABLE_SCORE,
        )
        return None

    valid_photos.sort(key=lambda x: x["score"], reverse=True)

    logger.info(
        "Selected and processed best photos",
        count=len(valid_photos),
        scores=[p["score"] for p in valid_photos],
    )

    return [(p["unique_id"], p["file_id"], p["bytes"]) for p in valid_photos]


# --- NEW: Identity Sorting and Centroid Logic ---

async def _get_best_face_embedding(img_bytes: bytes) -> Optional[np.ndarray]:
    """
    Extracts the ArcFace embedding from the largest face in an image.
    This is an async wrapper around a synchronous, CPU-bound function.
    """
    def sync_get_embedding():
        app = _get_face_analysis_app()
        img_bgr = load_image_bgr_from_bytes(img_bytes)
        if img_bgr is None:
            return None
            
        faces = app.get(img_bgr)
        if not faces:
            return None
        
        # Choose the largest face by area
        areas = [(max(0, f.bbox[2] - f.bbox[0]) * max(0, f.bbox[3] - f.bbox[1])) for f in faces]
        best_face = faces[np.argmax(areas)]
        
        emb = best_face.normed_embedding
        return emb.astype(np.float32) if emb is not None and emb.size > 0 else None

    return await asyncio.to_thread(sync_get_embedding)

def _find_outlier_index(embs: np.ndarray) -> int:
    """Finds the single impostor by lowest average cosine similarity."""
    if embs.shape[0] <= 2: # Not enough data to find an outlier
        return -1
    S = embs @ embs.T
    np.fill_diagonal(S, 0.0)
    mean_sim = S.mean(axis=1)
    return int(np.argmin(mean_sim))

def _build_identity_centroid(embs: np.ndarray, outlier_idx: int = -1) -> np.ndarray:
    """Builds a robust, normalized identity centroid from inlier embeddings."""
    if outlier_idx != -1 and embs.shape[0] > 1:
        inlier_mask = np.ones(embs.shape[0], dtype=bool)
        inlier_mask[outlier_idx] = False
        embs_for_centroid = embs[inlier_mask]
    else:
        embs_for_centroid = embs

    centroid = embs_for_centroid.mean(axis=0)
    norm = np.linalg.norm(centroid)
    return centroid / max(norm, 1e-12)


async def calculate_identity_centroid(image_bytes_list: List[bytes]) -> Optional[np.ndarray]:
    """
    Calculates a single, robust identity vector (centroid) from a list of images.

    This function extracts face embeddings from all provided images, optionally
    removes an outlier, and averages the remaining embeddings to create a
    stable representation of a person's identity.

    Args:
        image_bytes_list: A list of image bytes, each expected to contain one person.

    Returns:
        A normalized NumPy array representing the identity centroid, or None if no
        valid faces could be processed.
    """
    if not image_bytes_list:
        return None
    
    embedding_tasks = [_get_best_face_embedding(b) for b in image_bytes_list]
    embeddings = await asyncio.gather(*embedding_tasks)
    
    valid_embeddings = [emb for emb in embeddings if emb is not None]
    if not valid_embeddings:
        logger.warning("Could not extract any valid face embeddings to calculate centroid.")
        return None
        
    embs_matrix = np.stack(valid_embeddings, axis=0)
    outlier_idx = _find_outlier_index(embs_matrix)
    
    centroid = _build_identity_centroid(embs_matrix, outlier_idx)
    logger.info("Calculated identity centroid.", num_embeddings=len(valid_embeddings), outlier_removed=outlier_idx != -1)
    return centroid


async def sort_and_filter_by_identity(
    photos_data: List[dict],
    target_count: int,
    min_similarity_score: float = 0.8
) -> List[dict]:
    """
    Sorts photos by identity, filters by a similarity score, and pads the list
    with duplicates of the best images to reach a target count.

    Args:
        photos_data: A list of dictionaries, each containing 'bytes' and identifiers.
        target_count: The exact number of photos to return.
        min_similarity_score: The minimum cosine similarity score to be considered a high-quality photo.

    Returns:
        A list of photo data dictionaries with exactly `target_count` items.
    """
    if not photos_data:
        return []
    
    # If we already have fewer photos than the target, we can't do much sorting.
    # The padding logic will handle this case, so we can proceed.
    
    log = logger.bind(num_photos=len(photos_data), target_count=target_count)
    log.info("Starting identity similarity analysis, filtering, and padding...")

    embedding_tasks = [_get_best_face_embedding(p['bytes']) for p in photos_data]
    results = await asyncio.gather(*embedding_tasks)

    valid_embeddings, valid_photos_data = [], []
    for i, emb in enumerate(results):
        if emb is not None:
            valid_embeddings.append(emb)
            valid_photos_data.append(photos_data[i])
            
    if len(valid_embeddings) < 1:
        log.warning("No valid faces found for similarity sorting. Cannot proceed.")
        # As a fallback, just return the first `target_count` items if they exist
        return photos_data[:target_count]

    embs_matrix = np.stack(valid_embeddings, axis=0)
    
    outlier_idx = _find_outlier_index(embs_matrix)
    centroid = _build_identity_centroid(embs_matrix, outlier_idx)
    similarities = embs_matrix @ centroid
    
    sorted_indices = np.argsort(-similarities)
    
    sorted_photos = [
        {**valid_photos_data[idx], 'similarity_score': float(similarities[idx])}
        for idx in sorted_indices
    ]

    # --- NEW: Filtering and Padding Logic ---

    # 1. Filter by the minimum score threshold
    high_quality_photos = [
        p for p in sorted_photos if p['similarity_score'] >= min_similarity_score
    ]
    log.info("Filtered photos by similarity score.", initial_count=len(sorted_photos), high_quality_count=len(high_quality_photos))

    # 2. Decide which list to use for the final selection (the high-quality one, or the original sorted one as a fallback)
    source_for_selection = high_quality_photos
    if not high_quality_photos:
        log.warning(
            "No photos met the similarity threshold. Using best available photos as a fallback.",
            threshold=min_similarity_score
        )
        source_for_selection = sorted_photos

    # 3. Pad or truncate the list to meet the target_count
    final_photos = []
    source_len = len(source_for_selection)

    if source_len >= target_count:
        # We have enough (or more than enough), so just take the best ones
        final_photos = source_for_selection[:target_count]
    else:
        # We have fewer than needed, so we must pad with duplicates
        final_photos = list(source_for_selection) # Start with all available high-quality photos
        while len(final_photos) < target_count:
            # Cycle through the source list to pick duplicates from the top
            index_to_copy = (len(final_photos) - source_len) % source_len
            # Create a copy to avoid modifying the original list in place
            photo_to_add = source_for_selection[index_to_copy].copy()
            final_photos.append(photo_to_add)
            
    log.info(
        "Identity analysis complete. Final photo selection prepared.",
        final_count=len(final_photos),
        similarity_scores=[round(p['similarity_score'], 4) for p in final_photos]
    )
    
    return final_photos
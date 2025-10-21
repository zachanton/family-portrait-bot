# aiogram_bot_template/services/similarity_scorer.py
import asyncio
import io
import math
import hashlib
import threading
from collections import OrderedDict
from typing import List, Optional, Tuple

import cv2
import mediapipe as mp
import numpy as np
import structlog
from PIL import Image, ImageOps

# Import insightface for advanced identity analysis
from insightface.app import FaceAnalysis

logger = structlog.get_logger(__name__)

# --- MediaPipe Initialization (only for Selfie Segmentation) ---
mp_selfie_seg = mp.solutions.selfie_segmentation

# --- InsightFace Singleton & Concurrency Control ---
_face_analysis_app: Optional[FaceAnalysis] = None
_FACE_APP_LOCK = threading.Lock() # Lock for thread-safe access to app.get()

def _get_face_analysis_app() -> FaceAnalysis:
    """Initializes and returns a singleton FaceAnalysis instance."""
    global _face_analysis_app
    with _FACE_APP_LOCK:
        if _face_analysis_app is None:
            logger.info("Initializing InsightFace model for the first time in this process...")
            app = FaceAnalysis(name="buffalo_l", providers=['CPUExecutionProvider'])
            app.prepare(ctx_id=0, det_size=(640, 640))
            _face_analysis_app = app
            logger.info("InsightFace model initialized successfully.")
    return _face_analysis_app

# --- Embedding Cache ---
class _EmbeddingCache:
    def __init__(self, maxsize: int = 2048):
        self.maxsize = maxsize
        self._store: OrderedDict[str, dict] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: str):
        with self._lock:
            if key in self._store:
                self._store.move_to_end(key)
                return self._store[key]
            return None

    def put(self, key: str, value: dict):
        with self._lock:
            self._store[key] = value
            self._store.move_to_end(key)
            if len(self._store) > self.maxsize:
                self._store.popitem(last=False)

_EMB_CACHE = _EmbeddingCache(maxsize=2048)

def _sha1_bytes(b: bytes) -> str:
    h = hashlib.sha1()
    h.update(b)
    return h.hexdigest()

# --- Processing constants ---
STANDARD_TILE_WIDTH = 576
STANDARD_TILE_HEIGHT = 512
MIN_FACE_AREA_RATIO = 0.05
TARGET_FACE_HEIGHT_RATIO = 0.55
VERTICAL_CENTER_OFFSET = -0.1
BACKGROUND_COLOR = (190, 190, 190)
KPS_TO_BBOX_HEIGHT_RATIO = 2.2 # Heuristic ratio between core face height (eyes-to-mouth) and full bbox height

class PhotoAnalysisResult(Tuple):
    """A type hint for the output of the analysis and processing function."""
    processed_image_bytes: bytes
    score: float
    file_unique_id: str
    file_id: str


# --- I/O Functions ---
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


# --- Image Processing Helpers ---

def _person_alpha_mask_improved(bgr: np.ndarray, t_fg=0.92, t_bg=0.18, feather_px=6) -> np.ndarray:
    h, w = bgr.shape[:2]
    with mp_selfie_seg.SelfieSegmentation(model_selection=1) as seg:
        res = seg.process(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
    if res is None or res.segmentation_mask is None: return np.ones((h, w), dtype=np.float32)
    prob = res.segmentation_mask.astype(np.float32)
    sure_fg = (prob >= t_fg).astype(np.uint8) * 255; sure_bg = (prob <= t_bg).astype(np.uint8) * 255
    kernel = np.ones((5, 5), np.uint8)
    sure_fg = cv2.morphologyEx(sure_fg, cv2.MORPH_CLOSE, kernel, iterations=1)
    sure_bg = cv2.morphologyEx(sure_bg, cv2.MORPH_CLOSE, kernel, iterations=1)
    dist_fg = cv2.distanceTransform(cv2.bitwise_not(sure_fg), cv2.DIST_L2, 3)
    dist_bg = cv2.distanceTransform(cv2.bitwise_not(sure_bg), cv2.DIST_L2, 3)
    a_unknown = dist_bg / (dist_bg + dist_fg + 1e-6); a_unknown = np.clip(a_unknown, 0.0, 1.0)
    alpha = np.where(sure_fg == 255, 1.0, np.where(sure_bg == 255, 0.0, a_unknown)).astype(np.float32)
    alpha_bi = cv2.bilateralFilter(alpha, d=7, sigmaColor=0.15, sigmaSpace=5)
    return cv2.GaussianBlur(alpha_bi, (0, 0), sigmaX=max(3, feather_px)/3.0, sigmaY=max(3, feather_px)/3.0)


def _composite_with_occlusion_masking(
    bgr_img: np.ndarray,
    target_face: dict,
    all_faces: List[dict]
) -> np.ndarray:
    """
    Isolates the main person by painting over other detected faces with a neutral color
    before applying a segmentation mask. This acts like a "spotlight" on the target person.
    """
    # 1. Create a mutable copy of the image that we can draw on.
    spotlight_img = bgr_img.copy()

    # 2. If there are other people, create a mask for them and paint them gray.
    if len(all_faces) > 1:
        h, w = bgr_img.shape[:2]
        occlusion_mask = np.zeros((h, w), dtype=np.uint8)
        for face in all_faces:
            if face.det_score != target_face.det_score:
                x1, y1, x2, y2 = map(int, face.bbox)
                cv2.rectangle(occlusion_mask, (x1, y1), (x2, y2), 255, -1)
        
        x1, y1, x2, y2 = map(int, target_face.bbox)
        cv2.rectangle(occlusion_mask, (x1, y1), (x2, y2), 0, -1)
        
        # Using numpy, paint the gray color onto our copy where the occlusion mask is active.
        spotlight_img[occlusion_mask == 255] = BACKGROUND_COLOR

    # 3. Now run the person segmentation on the "cleaned" image.
    # The grayed-out areas will be treated as background.
    person_alpha = _person_alpha_mask_improved(spotlight_img)
    final_alpha_3ch = person_alpha[:, :, None]

    # 4. Composite the segmented person from the cleaned image against a uniform background.
    bg_img = np.full_like(bgr_img, BACKGROUND_COLOR, dtype=np.uint8)
    composited = (final_alpha_3ch * spotlight_img.astype(np.float32) + (1.0 - final_alpha_3ch) * bg_img.astype(np.float32))
    
    return composited.astype(np.uint8)


# --- Alignment and Cropping Helpers ---

def _calc_roll_angle_from_kps(kps: np.ndarray) -> float:
    if kps is None or kps.shape != (5, 2): return 0.0
    left_eye, right_eye = kps[0], kps[1]
    dy, dx = float(right_eye[1] - left_eye[1]), float(right_eye[0] - left_eye[0])
    return math.degrees(math.atan2(dy, dx))

def _rotate_image_around_point(img: np.ndarray, center: Tuple, angle: float) -> Tuple[np.ndarray, np.ndarray]:
    h, w = img.shape[:2]
    M = cv2.getRotationMatrix2D(tuple(map(float, center)), angle, 1.0)
    return cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_LINEAR,
                             borderMode=cv2.BORDER_CONSTANT, borderValue=BACKGROUND_COLOR), M

def _affine_transform_points(M: np.ndarray, pts: Optional[np.ndarray]) -> Optional[np.ndarray]:
    if pts is None: return None
    return cv2.transform(np.array([pts]), M)[0].astype(np.float32)

def _transform_bbox_by_affine(M: np.ndarray, bbox: Tuple) -> Tuple[float, float, float, float]:
    x1, y1, x2, y2 = bbox
    corners = np.array([[x1,y1],[x2,y1],[x2,y2],[x1,y2]], dtype=np.float32)
    tc = _affine_transform_points(M, corners)
    return float(np.min(tc[:,0])), float(np.min(tc[:,1])), float(np.max(tc[:,0])), float(np.max(tc[:,1]))

def _get_stable_face_height_from_kps(kps: np.ndarray) -> float:
    """Calculates a stable face height metric from keypoints (eyes to mouth distance)."""
    eye_mid_y = (kps[0][1] + kps[1][1]) / 2
    mouth_mid_y = (kps[3][1] + kps[4][1]) / 2
    core_height = abs(mouth_mid_y - eye_mid_y)
    return core_height * KPS_TO_BBOX_HEIGHT_RATIO

def _crop_and_resize_to_standard(
    bgr: np.ndarray, bbox: Tuple, kps: np.ndarray, target_w: int, target_h: int
) -> np.ndarray:
    """Crops and resizes via a single affine transform for consistent face scale."""
    stable_face_h_src = _get_stable_face_height_from_kps(kps)
    face_cx_src, face_cy_src = (bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2
    face_h_dst = target_h * TARGET_FACE_HEIGHT_RATIO
    scale = face_h_dst / stable_face_h_src if stable_face_h_src > 0 else 1.0
    center_y_adjusted = face_cy_src + (stable_face_h_src * VERTICAL_CENTER_OFFSET)
    
    src_pts = np.array([
        [face_cx_src - (0.5 * target_w / scale), center_y_adjusted - (0.5 * target_h / scale)],
        [face_cx_src + (0.5 * target_w / scale), center_y_adjusted - (0.5 * target_h / scale)],
        [face_cx_src - (0.5 * target_w / scale), center_y_adjusted + (0.5 * target_h / scale)],
    ], dtype=np.float32)
    dst_pts = np.array([[0, 0], [target_w, 0], [0, target_h]], dtype=np.float32)
    
    M = cv2.getAffineTransform(src_pts, dst_pts)
    return cv2.warpAffine(bgr, M, (target_w, target_h), flags=cv2.INTER_LINEAR,
                          borderMode=cv2.BORDER_CONSTANT, borderValue=BACKGROUND_COLOR)

# --- Image Quality Scoring ---

def _compute_image_quality_score(bbox: Tuple) -> float:
    """
    Calculates the quality score as the absolute area of the bounding box in pixels.
    """
    x1, y1, x2, y2 = bbox
    area = (x2 - x1) * (y2 - y1)
    return float(max(0, area))


# --- Core Logic ---

def _analyze_and_process_one_photo(
    img_bgr: np.ndarray, file_unique_id: str, file_id: str
) -> List[PhotoAnalysisResult]:
    app = _get_face_analysis_app()
    with _FACE_APP_LOCK:
        all_faces = app.get(img_bgr)

    if not all_faces:
        return []

    analysis_results: List[PhotoAnalysisResult] = []
    
    for i, face in enumerate(all_faces):
        bbox = tuple(map(float, face.bbox))
        kps = face.kps.astype(np.float32) if face.kps is not None else None
        if kps is None:
            continue

        angle = _calc_roll_angle_from_kps(kps)
        face_center = ((bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2)
        
        aligned_img, M = _rotate_image_around_point(img_bgr, face_center, angle)
        
        clean_aligned_img = _composite_with_occlusion_masking(aligned_img, face, all_faces)

        bbox_t = _transform_bbox_by_affine(M, bbox)
        kps_t = _affine_transform_points(M, kps)

        processed_img = _crop_and_resize_to_standard(
            clean_aligned_img, bbox_t, kps_t, STANDARD_TILE_WIDTH, STANDARD_TILE_HEIGHT
        )
        
        processed_bytes = convert_bgr_to_jpeg_bytes(processed_img)

        quality_score = _compute_image_quality_score(bbox)
        
        final_score = quality_score
        
        face_unique_id = f"{file_unique_id}_face{i}"
        
        logger.debug("Analyzed face from photo", face_unique_id=face_unique_id, score=round(final_score, 4))
        
        analysis_results.append(
            PhotoAnalysisResult((processed_bytes, float(final_score), face_unique_id, file_id))
        )
    
    return analysis_results


# --- REFACTORED IMPLEMENTATION ---
def select_best_photos_and_process_sync(
    photo_inputs: List[Tuple[bytes, str, str]],
) -> Optional[List[Tuple[str, str, bytes]]]:
    """
    Analyzes raw photos, processes all detected faces, filters them by minimum size,
    then uses identity-based clustering and sorting to select the best portraits
    of the main subject.

    Args:
        photo_inputs: A list of tuples, each containing (photo_bytes, unique_id, file_id).

    Returns:
        A sorted list of tuples (unique_id, file_id, processed_photo_bytes) for the
        main subject, or None if no consistent identity is found.
    """
    if not photo_inputs:
        return None

    MIN_ACCEPTABLE_SCORE = 150*150  # Minimum face area in pixels (e.g., ~150x150 px)

    # 1. Detect, crop, and standardize all faces from all input images.
    all_results: List[PhotoAnalysisResult] = []
    for b, uid, fid in photo_inputs:
        img = load_image_bgr_from_bytes(b)
        if img is not None:
            try:
                analysis_results_list = _analyze_and_process_one_photo(img, uid, fid)
                if analysis_results_list:
                    all_results.extend(analysis_results_list)
            except Exception as e:
                logger.warning("Photo processing failed for one image", file_unique_id=uid, exc_info=e)

    if not all_results:
        logger.warning("No faces were detected in any of the provided photos.")
        return None
    
    # 2. Pre-filter by face size (quality score).
    photos_data_for_sorting = [
        {
            "bytes": res[0],
            "quality_score": res[1],
            "unique_id": res[2],
            "file_id": res[3]
        } for res in all_results if res[1] >= MIN_ACCEPTABLE_SCORE
    ]

    if not photos_data_for_sorting:
        logger.warning("No faces met the minimum quality score.", threshold=MIN_ACCEPTABLE_SCORE)
        return None

    log = logger.bind(
        total_faces=len(all_results),
        faces_after_size_filter=len(photos_data_for_sorting)
    )
    log.info("Initial size-based filtering complete.")

    # 3. Delegate to the dedicated identity filtering and sorting function.
    # We pass a target_count equal to the number of photos to ensure it sorts
    # all of them without truncating or duplicating.
    sorted_photos = sort_and_filter_by_identity_sync(
        photos_data_for_sorting,
        target_count=len(photos_data_for_sorting)
    )

    if not sorted_photos:
        logger.warning("Identity analysis resulted in an empty photo list.")
        return None

    # 4. Format the output to the expected tuple format.
    return [(p["unique_id"], p["file_id"], p["bytes"]) for p in sorted_photos]


# --- Robust Identity Centroid and Sorting Logic ---

def _extract_face_features_sync(img_bytes: bytes) -> Optional[dict]:
    """
    Synchronous version of face feature extraction.
    This function is designed to be run in a worker process.
    """
    key = _sha1_bytes(img_bytes)
    if (cached := _EMB_CACHE.get(key)) is not None: return cached
    app = _get_face_analysis_app()
    img = load_image_bgr_from_bytes(img_bytes)
    if img is None: return None
    with _FACE_APP_LOCK: faces = app.get(img)
    if not faces: return None
    best_face = max(faces, key=lambda f: (f.bbox[2]-f.bbox[0])*(f.bbox[3]-f.bbox[1]))
    if best_face.normed_embedding is None: return None
    result = {"embedding": best_face.normed_embedding.astype(np.float32), "bbox": tuple(map(float, best_face.bbox)),
              "kps": best_face.kps.astype(np.float32) if best_face.kps is not None else None,
              "det_score": float(best_face.det_score), "image_sha1": key}
    _EMB_CACHE.put(key, result)
    return result

def _cosine_sim_matrix(embs: np.ndarray) -> np.ndarray: return embs @ embs.T

def _largest_component_by_threshold(embs: np.ndarray, tau: float=0.35) -> np.ndarray:
    n = embs.shape[0]
    if n <= 1: return np.arange(n)
    adj = (_cosine_sim_matrix(embs) >= tau)
    visited, best_comp = set(), []
    for i in range(n):
        if i not in visited:
            comp, q = [], [i]; visited.add(i)
            while q:
                u = q.pop(0); comp.append(u)
                for v in np.where(adj[u])[0]:
                    if v not in visited: visited.add(v); q.append(v)
            if len(comp) > len(best_comp): best_comp = comp
    return np.array(sorted(best_comp))

def _mad_outliers_by_mean_similarity(embs: np.ndarray, z: float=3.5) -> np.ndarray:
    if embs.shape[0] <= 2: return np.array([])
    S = _cosine_sim_matrix(embs); np.fill_diagonal(S, np.nan)
    mean_sim = np.nanmean(S, axis=1)
    med = np.nanmedian(mean_sim); mad = np.nanmedian(np.abs(mean_sim - med)) + 1e-12
    return np.where((med - mean_sim) / mad > z)[0]

def _geometric_median(pts: np.ndarray, eps: float=1e-6) -> np.ndarray:
    x = pts.mean(axis=0)
    for _ in range(200):
        w = 1.0 / (np.linalg.norm(pts - x, axis=1) + 1e-12)
        x_new = (pts * w[:, None]).sum(axis=0) / w.sum()
        if np.linalg.norm(x_new - x) < eps: x = x_new; break
        x = x_new
    return x / max(np.linalg.norm(x), 1e-12)

def _build_robust_centroid(embs: np.ndarray) -> np.ndarray:
    """
    Calculates a robust centroid from a pre-filtered set of embeddings.
    """
    if embs.shape[0] == 0:
        logger.error("Attempted to build centroid from zero embeddings. This should not happen.")
        # Return a zero vector as a safe fallback, though this indicates an upstream issue.
        return np.zeros(embs.shape[1] if embs.ndim > 1 else 512, dtype=np.float32)
    if embs.shape[0] == 1:
        return embs[0]
        
    log = logger.bind(initial_count=embs.shape[0])
    
    c = embs.mean(axis=0); c /= max(np.linalg.norm(c), 1e-12)
    final_inliers = embs

    for i in range(2):
        sims = embs @ c
        quantile_threshold = np.quantile(sims, 0.20)
        trimmed_embs = embs[sims >= quantile_threshold]

        if trimmed_embs.shape[0] > 0:
            c = trimmed_embs.mean(axis=0)
            c /= max(np.linalg.norm(c), 1e-12)
            final_inliers = trimmed_embs
        
        log = log.bind(**{f"after_trim_iter_{i+1}": trimmed_embs.shape[0]})
    
    log.info("Robust centroid refinement steps")
    return _geometric_median(final_inliers)

def calculate_identity_centroid_sync(image_bytes_list: List[bytes]) -> Optional[np.ndarray]:
    """
    Synchronous version of identity centroid calculation for worker processes.
    """
    if not image_bytes_list: return None
    
    feats = [_extract_face_features_sync(b) for b in image_bytes_list]
    embs = [f["embedding"] for f in feats if f and f.get("embedding") is not None]
    if not embs:
        logger.warning("Could not extract any valid face embeddings for centroid."); return None
    
    embeddings_stack = np.stack(embs)
    log = logger.bind(initial_count=embeddings_stack.shape[0])
    
    inlier_indices = _largest_component_by_threshold(embeddings_stack)
    if inlier_indices.size == 0:
        log.warning("No cohesive identity group found, falling back to all embeddings.")
        inlier_embs = embeddings_stack
    else:
        inlier_embs = embeddings_stack[inlier_indices]
    log = log.bind(after_component_filter=inlier_embs.shape[0])

    if inlier_embs.shape[0] == 0:
        log.warning("All embeddings filtered out, falling back to initial mean."); c = embeddings_stack.mean(axis=0)
        return c / max(np.linalg.norm(c), 1e-12)

    return _build_robust_centroid(inlier_embs)


def sort_and_filter_by_identity_sync(
    photos_data: List[dict], target_count: int
) -> List[dict]:
    """
    Filters a list of processed photos to find a single, coherent identity,
    then sorts them by similarity to a robust identity centroid.

    Args:
        photos_data: List of dicts, each must contain a 'bytes' key with the processed image.
        target_count: The desired number of photos to return. If more are available, the
                      list is truncated. If fewer are available, the best ones are duplicated.

    Returns:
        A sorted and filtered list of photo dicts, conforming to the target_count.
    """
    if not photos_data: return []
    log = logger.bind(initial_count=len(photos_data), target_count=target_count)
    log.info("Starting identity filtering and sorting...")
    
    # Use 'quality_score' (bbox area) for secondary sorting later
    for p in photos_data:
        p.setdefault('quality_score', 0)

    # This loop is cheap because of caching in _extract_face_features_sync
    feats = [_extract_face_features_sync(p['bytes']) for p in photos_data]
    
    valid_data = [(p, f) for p, f in zip(photos_data, feats) if f and f.get("embedding") is not None]
    if not valid_data:
        log.warning("No valid faces found for identity analysis. Returning original photos sorted by quality.")
        return sorted(photos_data, key=lambda p: p['quality_score'], reverse=True)[:target_count]
    
    all_photos, all_embs_list = zip(*[(p, f["embedding"]) for p, f in valid_data])
    all_embs = np.stack(all_embs_list)

    inlier_indices = _largest_component_by_threshold(all_embs)
    if inlier_indices.size < len(all_photos):
        log.info("Filtered by largest component", before=len(all_photos), after=inlier_indices.size)

    component_embs = all_embs[inlier_indices]
    mad_outlier_indices_in_component = _mad_outliers_by_mean_similarity(component_embs)
    
    final_inlier_indices = np.delete(inlier_indices, mad_outlier_indices_in_component)
    if final_inlier_indices.size < inlier_indices.size:
        log.info("Filtered by MAD outliers", before=inlier_indices.size, after=final_inlier_indices.size)
    
    if final_inlier_indices.size == 0:
        log.warning("All photos were filtered out as outliers. Falling back to using largest component.")
        if inlier_indices.size > 0:
            inlier_photos = [all_photos[i] for i in inlier_indices]
            inlier_embs = all_embs[inlier_indices]
        else: # Ultimate fallback
            inlier_photos = list(all_photos)
            inlier_embs = all_embs
    else:
        inlier_photos = [all_photos[i] for i in final_inlier_indices]
        inlier_embs = all_embs[final_inlier_indices]

    centroid = _build_robust_centroid(inlier_embs)
    similarities = inlier_embs @ centroid
    
    for photo, sim_score in zip(inlier_photos, similarities):
        photo['similarity_score'] = float(sim_score)

    # Primary sort by identity similarity, secondary by original face size
    sorted_photos = sorted(
        inlier_photos,
        key=lambda p: p['similarity_score'],
        reverse=True
    )

    final_photos = []
    for p in sorted_photos:
        if p['similarity_score'] >= 0.8:
            final_photos.append(p)
        
    final_photos = list(final_photos[:4])
    
    if 0 < len(final_photos) < 4:
        num_needed = target_count - len(final_photos)
        duplicates_to_add = [
            dict(final_photos[i % len(final_photos)]) for i in range(num_needed)
        ]
        final_photos.extend(duplicates_to_add)
        log.info("Duplicated best photos to meet target count.", needed=num_needed, final_count=len(final_photos))

    log.info("Identity analysis complete.", final_count=len(final_photos), scores=[round(p.get('similarity_score', 0), 4) for p in final_photos])
    return final_photos
# aiogram_bot_template/services/photo_processing.py
import cv2
import io
import numpy as np
import mediapipe as mp

import structlog
from typing import Optional, List, Dict
from PIL import Image, ImageOps
import threading

# Import insightface for face detection and alignment
from insightface.app import FaceAnalysis

logger = structlog.get_logger(__name__)

# --- InsightFace Singleton & Concurrency Control ---
# This logic is duplicated from similarity_scorer to avoid circular dependencies.
# In a larger project, this could be moved to a shared utility module.
_face_analysis_app: Optional[FaceAnalysis] = None
_FACE_APP_LOCK = threading.Lock()

def _get_face_analysis_app() -> FaceAnalysis:
    """Initializes and returns a singleton FaceAnalysis instance."""
    global _face_analysis_app
    with _FACE_APP_LOCK:
        if _face_analysis_app is None:
            logger.info("Initializing InsightFace model for photo processing...")
            app = FaceAnalysis(name="buffalo_l", providers=['CPUExecutionProvider'])
            app.prepare(ctx_id=0, det_size=(640, 640))
            _face_analysis_app = app
            logger.info("InsightFace model initialized successfully for photo processing.")
    return _face_analysis_app


# --- Collage and Stacking constants ---
TIKTOK_CANVAS_W = 1152
TIKTOK_CANVAS_H = 1024
BACKGROUND_COLOR_TUPLE = (190, 190, 190)
STANDARD_FACE_WIDTH = 512
STANDARD_FACE_HEIGHT = 512
TARGET_FACE_HEIGHT_RATIO = 0.45  # Place the face taking up 45% of the canvas height
VERTICAL_CENTER_OFFSET = -0.08 # Shift the face slightly up from the geometric center



mp_face_detection = mp.solutions.face_detection


# --- I/O Functions ---
def load_image_bgr_from_bytes(data: bytes) -> Optional[np.ndarray]:
    """Loads an image from bytes into a BGR NumPy array."""
    try:
        img = Image.open(io.BytesIO(data))
        img = ImageOps.exif_transpose(img)
        if img.mode != 'RGB':
            img = img.convert('RGB')
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

# --- Collage-Specific Helpers (logic that requires multiple images) ---

def _variance_of_laplacian(bgr: np.ndarray) -> float:
    """Calculates the sharpness of an image."""
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(gray, cv2.CV_64F, ksize=3).var())

def _choose_reference_index(tiles: List[np.ndarray]) -> int:
    """Selects the best tile from a list to be the color reference."""
    best_idx, best_score = 0, -1e9
    for i, t in enumerate(tiles):
        sharp = _variance_of_laplacian(t)
        mean = float(cv2.cvtColor(t, cv2.COLOR_BGR2GRAY).mean())
        brightness_bonus = 1.0 - abs(mean - 128.0) / 128.0
        score = 0.8 * sharp + 0.2 * (1000.0 * brightness_bonus)
        if score > best_score:
            best_score, best_idx = score, i
    return best_idx

def _skin_mask_ycrcb(bgr: np.ndarray) -> np.ndarray:
    """Creates a conservative skin mask in YCrCb color space."""
    ycrcb = cv2.cvtColor(bgr, cv2.COLOR_BGR2YCrCb)
    skin = cv2.inRange(ycrcb, (0, 133, 77), (255, 173, 127))
    skin = cv2.medianBlur(skin, 5)
    return (skin.astype(np.float32) / 255.0)


def _create_mask_from_gray_bg(bgr: np.ndarray, bg_color: tuple, threshold: int = 15) -> np.ndarray:
    """
    Creates a precise person mask by selecting all pixels that are NOT the background color.
    This is fast and accurate because we know the exact background color.
    
    Args:
        bgr: The source image with a uniform gray background.
        bg_color: The BGR tuple of the background color.
        threshold: Tolerance for color differences due to compression artifacts.

    Returns:
        A single-channel float32 mask (0.0 for background, 1.0 for person).
    """
    diff = cv2.absdiff(bgr, bg_color)
    total_diff = np.sum(diff, axis=2)
    mask = (total_diff > threshold).astype(np.uint8) * 255
    
    kernel = np.ones((5, 5), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    
    return (mask.astype(np.float32) / 255.0)[:, :, np.newaxis]

# --- MODIFIED ---
def _reinhard_color_transfer_masked(src_bgr: np.ndarray, ref_bgr: np.ndarray, alpha: float = 0.6) -> np.ndarray:
    """
    Transfers color from a reference image to a source image, applying a blended
    correction ONLY to the person, leaving the background untouched.
    """
    src_skin_mask = _skin_mask_ycrcb(src_bgr)
    ref_skin_mask = _skin_mask_ycrcb(ref_bgr)

    def _stats_lab(bgr, mask):
        lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB).astype(np.float32)
        w = np.clip(mask.astype(np.float32), 0.0, 1.0)
        w3 = np.dstack([w, w, w]); tot = w.sum() + 1e-6
        mean = (lab * w3).reshape(-1, 3).sum(0) / tot
        std  = np.sqrt((((lab - mean) * w3) ** 2).reshape(-1, 3).sum(0) / tot + 1e-6)
        return lab, mean, std

    src_lab, sm, ss = _stats_lab(src_bgr, src_skin_mask)
    _, rm, rs = _stats_lab(ref_bgr, ref_skin_mask)
    
    out = np.empty_like(src_lab)
    for i in range(3):
        ch = src_lab[..., i]
        ch = (ch - sm[i]) / (ss[i] if ss[i] > 1e-6 else 1.0)
        ch = ch * (rs[i] if rs[i] > 1e-6 else 1.0) + rm[i]
        out[..., i] = ch
    
    out = np.clip(out, 0, 255).astype(np.uint8)
    out_bgr = cv2.cvtColor(out, cv2.COLOR_LAB2BGR)

    # --- THE FIX IS HERE ---
    # 1. First, create a 'softened' version of the color correction by blending
    #    the aggressive result with the original image. This prevents oversaturation.
    blended_bgr = cv2.addWeighted(out_bgr, alpha, src_bgr, 1.0 - alpha, 0.0)

    # 2. Then, create a precise mask of the person from the original image.
    person_mask = _create_mask_from_gray_bg(src_bgr, BACKGROUND_COLOR_TUPLE)

    # 3. Finally, composite the blended result onto the original image using the mask.
    #    This applies the softened correction only to the person, preserving the perfect gray background.
    final_bgr = (person_mask * blended_bgr.astype(np.float32) + (1.0 - person_mask) * src_bgr.astype(np.float32)).astype(np.uint8)
    
    return final_bgr


# --- Public API ---

def create_portrait_collage_from_bytes(processed_tiles_bytes: List[bytes]) -> Optional[bytes]:
    """
    Assembles a 2x2 portrait collage from a list of pre-processed image tiles.

    This function expects exactly 4 byte strings, each representing a standardized
    576x512 tile with a neutral gray background. Its responsibilities are:
      1) Select the best tile as a color reference.
      2) Apply color transfer from the reference to the other three tiles.
      3) Assemble the final 2x2 collage (1152x1024).
    
    Args:
        processed_tiles_bytes: A list of 4 byte strings for the pre-processed tiles.

    Returns:
        The final collage image as JPEG bytes, or None on failure.
    """
    if not processed_tiles_bytes or len(processed_tiles_bytes) != 4:
        logger.warning("Exactly 4 pre-processed image tiles are required for the collage.")
        return None

    try:
        tiles = [load_image_bgr_from_bytes(data) for data in processed_tiles_bytes]
        if any(t is None for t in tiles):
            raise ValueError("Failed to load one or more pre-processed tiles from bytes.")

        ref_idx = _choose_reference_index(tiles)
        ref_tile = tiles[ref_idx]
        
        final_tiles = []
        for i, t in enumerate(tiles):
            if i == ref_idx:
                final_tiles.append(t)
            else:
                final_tiles.append(_reinhard_color_transfer_masked(t, ref_tile))
        
        tile_h, tile_w, _ = final_tiles[0].shape
        canvas = np.full((TIKTOK_CANVAS_H, TIKTOK_CANVAS_W, 3), BACKGROUND_COLOR_TUPLE, dtype=np.uint8)
        
        canvas[0:tile_h, 0:tile_w] = final_tiles[0]
        canvas[0:tile_h, tile_w:TIKTOK_CANVAS_W] = final_tiles[1]
        canvas[tile_h:TIKTOK_CANVAS_H, 0:tile_w] = final_tiles[2]
        canvas[tile_h:TIKTOK_CANVAS_H, tile_w:TIKTOK_CANVAS_W] = final_tiles[3]

        return convert_bgr_to_jpeg_bytes(canvas, quality=95)

    except Exception:
        logger.exception("A critical error occurred in create_portrait_collage_from_bytes.")
        return None


def split_and_stack_image_bytes(image_bytes: bytes) -> tuple[bytes | None, bytes | None]:
    """
    Splits a horizontally concatenated image (front + side view) into two separate images.
    """
    try:
        img_bgr = load_image_bgr_from_bytes(image_bytes)
        if img_bgr is None:
            return None, None
        h, w = img_bgr.shape[:2]
        midpoint = w // 2
        front_view = img_bgr[:, :midpoint]
        side_view = img_bgr[:, midpoint:]
        return convert_bgr_to_jpeg_bytes(front_view), convert_bgr_to_jpeg_bytes(side_view)
    except Exception:
        logger.exception("Failed to split image into front and side views.")
        return None, None


def _analyze_image_safe_zone(img: np.ndarray) -> Dict[str, int]:
    """
    Анализирует изображение, находит лица и возвращает "безопасную" вертикальную зону.
    """
    h, w, _ = img.shape
    
    safe_zone = {'y_start': int(h * 0.1), 'y_end': int(h * 0.9)}

    with mp_face_detection.FaceDetection(model_selection=1, min_detection_confidence=0.5) as face_detection:
        results = face_detection.process(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        if results.detections:
            all_y_coords = []
            for detection in results.detections:
                box = detection.location_data.relative_bounding_box
                all_y_coords.append(int(box.ymin * h))
                all_y_coords.append(int((box.ymin + box.height) * h))
            
            y_min_head = min(all_y_coords)
            y_max_head = max(all_y_coords)
            
            head_height = y_max_head - y_min_head
            safe_zone['y_start'] = max(0, y_min_head - int(head_height * 0.5))
            safe_zone['y_end'] = min(h, y_max_head + int(head_height * 0.3))

    safe_zone['height'] = safe_zone['y_end'] - safe_zone['y_start']
    safe_zone['headroom'] = safe_zone['y_start']
    safe_zone['chinroom'] = h - safe_zone['y_end']
    return safe_zone

def _crop_to_center_face(img: np.ndarray, target_h: int) -> np.ndarray:
    """
    Обрезает изображение до target_h, стараясь сохранить лицо в центре.
    """
    original_h, _, _ = img.shape
    if original_h <= target_h:
        return img

    safe_zone = _analyze_image_safe_zone(img)
    face_center_y = safe_zone['y_start'] + safe_zone['height'] / 2

    crop_y_start = int(face_center_y - target_h / 2)
    crop_y_start = max(0, min(crop_y_start, original_h - target_h))
    
    return img[crop_y_start : crop_y_start + target_h, :]


def stack_three_images(
    img_top_bytes: bytes,
    img_middle_bytes: bytes,
    img_bottom_bytes: bytes,
) -> bytes:
    """
    Stacks three images vertically after resizing them to a common width.
    """
    img_mom = load_image_bgr_from_bytes(img_top_bytes)
    img_dad = load_image_bgr_from_bytes(img_middle_bytes)
    img_child = load_image_bgr_from_bytes(img_bottom_bytes)
    
    target_width = min(img_mom.shape[1], img_dad.shape[1])
    
    def resize_to_width(img, new_width):
        h, w, _ = img.shape
        scale = new_width / w
        return cv2.resize(img, (new_width, int(h * scale)), interpolation=cv2.INTER_AREA)

    mom_resized = resize_to_width(img_mom, target_width)
    dad_resized = resize_to_width(img_dad, target_width)
    child_resized = resize_to_width(img_child, target_width // 2)
    
    safe_mom = _analyze_image_safe_zone(mom_resized)
    safe_dad = _analyze_image_safe_zone(dad_resized)
    safe_child = _analyze_image_safe_zone(child_resized)

    final_width = target_width
    final_height = int(final_width * 16 / 9)

    total_safe_height = safe_mom['height'] + safe_dad['height'] + safe_child['height']
    
    total_croppable_space = (safe_mom['headroom'] + safe_mom['chinroom'] + 
                             safe_dad['headroom'] + safe_dad['chinroom'] + 
                             safe_child['headroom'] + safe_child['chinroom'])
    
    extra_height_to_distribute = final_height - total_safe_height

    if extra_height_to_distribute < 0:
        scale = final_height / total_safe_height
        h_mom = int(safe_mom['height'] * scale)
        h_dad = int(safe_dad['height'] * scale)
        h_child = final_height - h_mom - h_dad
    else:
        def get_share(safe_zone):
            return (safe_zone['headroom'] + safe_zone['chinroom']) / total_croppable_space if total_croppable_space > 0 else 1/3

        extra_mom = int(extra_height_to_distribute * get_share(safe_mom))
        extra_dad = int(extra_height_to_distribute * get_share(safe_dad))
        extra_child = final_height - total_safe_height - extra_mom - extra_dad

        h_mom = safe_mom['height'] + extra_mom
        h_dad = safe_dad['height'] + extra_dad
        h_child = safe_child['height'] + extra_child

    mom_final = _crop_to_center_face(mom_resized, h_mom)
    dad_final = _crop_to_center_face(dad_resized, h_dad)
    child_final = _crop_to_center_face(child_resized, h_child)
    
    canvas = np.full((final_height, final_width, 3), 128, dtype=np.uint8)
    
    current_y = 0
    canvas[current_y : current_y + h_mom, :] = mom_final
    current_y += h_mom
    canvas[current_y : current_y + h_dad, :] = dad_final
    current_y += h_dad
    child_h, child_w, _ = child_final.shape
    canvas[current_y : current_y + child_h, 0 : child_w] = child_final

    return convert_bgr_to_jpeg_bytes(canvas)


def stack_two_images(
    img_top_bytes: bytes,
    img_bottom_bytes: bytes,
) -> bytes:
    """
    Stacks two images vertically after resizing them to a common width.
    """
    img_mom = load_image_bgr_from_bytes(img_top_bytes)
    img_dad = load_image_bgr_from_bytes(img_bottom_bytes)

    target_width = min(img_mom.shape[1], img_dad.shape[1])
    
    def resize_to_width(img, new_width):
        h, w, _ = img.shape
        scale = new_width / w
        return cv2.resize(img, (new_width, int(h * scale)), interpolation=cv2.INTER_AREA)

    mom_resized = resize_to_width(img_mom, target_width)
    dad_resized = resize_to_width(img_dad, target_width)
    
    final_height = mom_resized.shape[0] + dad_resized.shape[0]

    canvas = np.full((final_height, target_width, 3), 128, dtype=np.uint8)
    
    current_y = 0
    canvas[current_y : current_y + mom_resized.shape[0], :] = mom_resized
    current_y += mom_resized.shape[0]
    canvas[current_y : current_y + dad_resized.shape[0], :] = dad_resized

    return convert_bgr_to_jpeg_bytes(canvas)


def _get_main_face(img_bgr: np.ndarray) -> Optional[dict]:
    """Detects faces and returns the largest one."""
    app = _get_face_analysis_app()
    with _FACE_APP_LOCK:
        faces = app.get(img_bgr)
    if not faces:
        return None
    # Return the face with the largest bounding box area
    return max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))


def _get_stable_face_height_from_kps(kps: np.ndarray) -> float:
    """Calculates a stable face height metric from keypoints (eyes to mouth distance)."""
    eye_mid_y = (kps[0][1] + kps[1][1]) / 2
    mouth_mid_y = (kps[3][1] + kps[4][1]) / 2
    # Heuristic ratio to approximate full face height from core features
    KPS_TO_BBOX_HEIGHT_RATIO = 2.2
    return abs(mouth_mid_y - eye_mid_y) * KPS_TO_BBOX_HEIGHT_RATIO


def _align_and_standardize_face(
    bgr: np.ndarray, target_w: int, target_h: int
) -> Optional[np.ndarray]:
    """
    Aligns and resizes a face to a standard canvas using an affine transform.

    This function detects the main face, calculates its stable height from keypoints,
    and then computes and applies a transformation to place the face at a
    consistent scale and position on a new canvas of target dimensions.

    Args:
        bgr: The source BGR image as a NumPy array.
        target_w: The width of the output canvas.
        target_h: The height of the output canvas.

    Returns:
        The transformed image on a standard canvas, or None if no face is detected.
    """
    face = _get_main_face(bgr)
    if face is None or face.kps is None:
        logger.warning("No face or keypoints detected for alignment.")
        # Fallback: simple resize if no face is found
        return cv2.resize(bgr, (target_w, target_h), interpolation=cv2.INTER_AREA)

    kps = face.kps.astype(np.float32)
    bbox = face.bbox
    
    # Use keypoints to get a stable measure of face height, less sensitive to expressions
    stable_face_h_src = _get_stable_face_height_from_kps(kps)
    face_cx_src = (bbox[0] + bbox[2]) / 2
    face_cy_src = (bbox[1] + bbox[3]) / 2

    # Define the target size and position of the face on the new canvas
    face_h_dst = target_h * TARGET_FACE_HEIGHT_RATIO
    scale = face_h_dst / stable_face_h_src if stable_face_h_src > 0 else 1.0
    
    # Adjust the vertical center to position the face according to portrait standards
    center_y_adjusted = face_cy_src + (stable_face_h_src * VERTICAL_CENTER_OFFSET)
    
    # Define source points for the affine transform based on the desired output crop
    src_pts = np.array([
        [face_cx_src - (0.5 * target_w / scale), center_y_adjusted - (0.5 * target_h / scale)],
        [face_cx_src + (0.5 * target_w / scale), center_y_adjusted - (0.5 * target_h / scale)],
        [face_cx_src - (0.5 * target_w / scale), center_y_adjusted + (0.5 * target_h / scale)],
    ], dtype=np.float32)

    # Define corresponding destination points on the new canvas
    dst_pts = np.array([[0, 0], [target_w, 0], [0, target_h]], dtype=np.float32)
    
    # Compute the transformation matrix and apply it
    M = cv2.getAffineTransform(src_pts, dst_pts)
    return cv2.warpAffine(bgr, M, (target_w, target_h), flags=cv2.INTER_LINEAR,
                          borderMode=cv2.BORDER_CONSTANT, borderValue=BACKGROUND_COLOR_TUPLE)

def stack_images_horizontally(
    img_left_bytes: bytes,
    img_right_bytes: bytes,
) -> Optional[bytes]:
    """
    Aligns two faces to a standard size and stacks them horizontally.

    Args:
        img_left_bytes: Bytes of the image for the left panel.
        img_right_bytes: Bytes of the image for the right panel.

    Returns:
        The combined image as JPEG bytes, or None on failure.
    """
    img_left = load_image_bgr_from_bytes(img_left_bytes)
    img_right = load_image_bgr_from_bytes(img_right_bytes)

    if img_left is None or img_right is None:
        logger.error("Could not load one or both images for horizontal stacking.")
        return None
        
    aligned_left = _align_and_standardize_face(img_left, STANDARD_FACE_WIDTH, STANDARD_FACE_HEIGHT)
    aligned_right = _align_and_standardize_face(img_right, STANDARD_FACE_WIDTH, STANDARD_FACE_HEIGHT)

    if aligned_left is None or aligned_right is None:
        logger.error("Face alignment failed for one or both images in horizontal stack.")
        return None

    combined_image = np.hstack((aligned_left, aligned_right))
    return convert_bgr_to_jpeg_bytes(combined_image)


def stack_images_vertically(
    img_top_bytes: bytes,
    img_bottom_bytes: bytes,
) -> Optional[bytes]:
    """
    Aligns two faces to a standard size and stacks them vertically.

    Args:
        img_top_bytes: Bytes of the image for the top panel.
        img_bottom_bytes: Bytes of the image for the bottom panel.

    Returns:
        The combined image as JPEG bytes, or None on failure.
    """
    img_top = load_image_bgr_from_bytes(img_top_bytes)
    img_bottom = load_image_bgr_from_bytes(img_bottom_bytes)

    if img_top is None or img_bottom is None:
        logger.error("Could not load one or both images for vertical stacking.")
        return None
        
    aligned_top = _align_and_standardize_face(img_top, STANDARD_FACE_WIDTH, STANDARD_FACE_HEIGHT)
    aligned_bottom = _align_and_standardize_face(img_bottom, STANDARD_FACE_WIDTH, STANDARD_FACE_HEIGHT)

    if aligned_top is None or aligned_bottom is None:
        logger.error("Face alignment failed for one or both images in vertical stack.")
        return None

    combined_image = np.vstack((aligned_top, aligned_bottom))
    return convert_bgr_to_jpeg_bytes(combined_image)

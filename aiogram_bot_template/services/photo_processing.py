# aiogram_bot_template/services/photo_processing.py
import cv2
import io
import math
import mediapipe as mp
import numpy as np
import structlog
from typing import Optional, Tuple, Dict, List
from PIL import Image, ImageOps

logger = structlog.get_logger(__name__)

# --- MediaPipe setup ---
mp_face_detection = mp.solutions.face_detection

# --- Cropping parameters ---
HEAD_VERTICAL_MARGIN_RATIO = 0.70
HEAD_HORIZONTAL_MARGIN_RATIO = 0.50

# --- Fixed canvas (must NOT change) ---
TIKTOK_CANVAS_W = 1440
TIKTOK_CANVAS_H = 1280
TIKTOK_BG_FALLBACK_BGR = (128, 128, 128) # Neutral gray background

# ---------------- I/O ----------------

def load_image_bgr_from_bytes(data: bytes) -> Optional[np.ndarray]:
    """
    Loads an image from bytes into a BGR NumPy array.

    Args:
        data: Image file bytes.

    Returns:
        A NumPy array in BGR format, or None if loading fails.
    """
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
    """
    Converts a BGR NumPy array to JPEG bytes in memory.

    Args:
        img_bgr: The image as a BGR NumPy array.
        quality: The JPEG quality setting (0-100).

    Returns:
        The JPEG image as bytes.
    """
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    buf = io.BytesIO()
    Image.fromarray(img_rgb).save(buf, format="JPEG", quality=quality, optimize=True)
    return buf.getvalue()

# --------------- Face prep ---------------

def _extract_and_prepare_faces(
    image_bytes_list: List[bytes],
    target_face_width: int
) -> List[np.ndarray]:
    """
    Detects faces, crops them with a generous margin, and resizes them to a normalized width.

    Args:
        image_bytes_list: A list of input images as bytes.
        target_face_width: The uniform width to which all cropped heads will be resized.

    Returns:
        A list of prepared face images as NumPy arrays.
    """
    prepared_faces = []
    # Initialize MediaPipe Face Detection.
    with mp_face_detection.FaceDetection(
        model_selection=1, min_detection_confidence=0.5
    ) as face_detection:
        for image_bytes in image_bytes_list:
            img_bgr = load_image_bgr_from_bytes(image_bytes)
            if img_bgr is None:
                continue

            img_h, img_w = img_bgr.shape[:2]
            img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
            results = face_detection.process(img_rgb)
            
            # Process only if exactly one face is detected for clarity.
            if not results.detections or len(results.detections) != 1:
                continue

            det = results.detections[0]
            box = det.location_data.relative_bounding_box
            face_x = int(box.xmin * img_w)
            face_y = int(box.ymin * img_h)
            face_w = int(box.width * img_w)
            face_h = int(box.height * img_h)

            # Add significant margins to ensure the entire head, hair, and neck are included.
            margin_v = int(face_h * HEAD_VERTICAL_MARGIN_RATIO)
            margin_h = int(face_w * HEAD_HORIZONTAL_MARGIN_RATIO)

            x1 = max(0, face_x - margin_h)
            y1 = max(0, face_y - margin_v)
            x2 = min(img_w, face_x + face_w + margin_h)
            y2 = min(img_h, face_y + face_h + margin_h)

            cropped = img_bgr[y1:y2, x1:x2]
            ch, cw = cropped.shape[:2]
            if cw == 0 or ch == 0:
                continue
            
            # Normalize all crops to the same width, maintaining aspect ratio.
            scale = target_face_width / cw
            new_h = max(1, int(ch * scale))
            resized = cv2.resize(cropped, (target_face_width, new_h), interpolation=cv2.INTER_AREA)

            prepared_faces.append(resized)
    return prepared_faces


# --------------- Packing Algorithm ---------------

def _pack_faces_onto_canvas(
    faces: List[np.ndarray],
    canvas_w: int,
    canvas_h: int,
    bg_color_bgr: Tuple[int, int, int]
) -> np.ndarray:
    """
    Arranges prepared face crops onto a solid gray canvas in a grid-like fashion,
    filling the entire space by repeating images if necessary.

    Args:
        faces: A list of prepared face images (NumPy arrays).
        canvas_w: The width of the final canvas.
        canvas_h: The height of the final canvas.
        bg_color_bgr: The background color for the canvas in BGR format.

    Returns:
        The final collage image as a NumPy array.
    """
    canvas = np.full((canvas_h, canvas_w, 3), bg_color_bgr, dtype=np.uint8)
    if not faces:
        return canvas

    # Assume all faces have been normalized to the same width.
    tile_w = faces[0].shape[1]
    
    # All tiles will be resized to the same average height for a uniform grid.
    avg_h = int(sum(f.shape[0] for f in faces) / len(faces))
    tile_h = avg_h

    if tile_w == 0 or tile_h == 0:
        return canvas

    # Calculate how many tiles can fit in the grid.
    cols = max(1, canvas_w // tile_w)
    rows = max(1, canvas_h // tile_h)
    
    # Resize all faces to the calculated uniform tile size.
    tiles = [cv2.resize(f, (tile_w, tile_h), interpolation=cv2.INTER_AREA) for f in faces]

    # Fill the grid, repeating tiles as needed.
    for r in range(rows):
        for c in range(cols):
            tile_idx = (r * cols + c) % len(tiles)
            tile = tiles[tile_idx]
            
            x_start, y_start = c * tile_w, r * tile_h
            x_end, y_end = x_start + tile_w, y_start + tile_h
            
            canvas[y_start:y_end, x_start:x_end] = tile

    # Fill any remaining space at the bottom or right edges if the division is not perfect.
    remaining_h = canvas_h - (rows * tile_h)
    if remaining_h > 0:
        for c in range(cols):
            tile_idx = (rows * cols + c) % len(tiles)
            tile_part = tiles[tile_idx][:remaining_h, :]
            x_start, y_start = c * tile_w, rows * tile_h
            x_end = x_start + tile_w
            canvas[y_start:y_start + remaining_h, x_start:x_end] = tile_part

    remaining_w = canvas_w - (cols * tile_w)
    if remaining_w > 0:
        for r in range(canvas_h):
            tile_idx = (r * cols) % len(tiles) # Simple logic to pick a tile
            row_in_tile = r % tile_h
            tile_strip = tiles[tile_idx][row_in_tile:row_in_tile+1, :remaining_w]
            if tile_strip.shape[1] < remaining_w:
                 # In case the strip is smaller, pad it to avoid errors.
                 tile_strip = cv2.copyMakeBorder(tile_strip, 0, 0, 0, remaining_w - tile_strip.shape[1], cv2.BORDER_CONSTANT, value=bg_color_bgr)
            
            x_start = cols * tile_w
            y_start = r
            canvas[y_start:y_start+1, x_start:x_start + remaining_w] = tile_strip

    return canvas

# --------------- Public API ---------------

def create_portrait_collage_from_bytes(image_bytes_list: List[bytes]) -> Optional[bytes]:
    """
    Creates a dense, grid-based collage of faces on a gray background.

    This function extracts all faces from the input images, normalizes them to a
    consistent size, and then tiles them onto a fixed-size canvas. The tiles
    are repeated as necessary to ensure the entire canvas is filled without gaps.

    Args:
        image_bytes_list: A list of source images, each as bytes.

    Returns:
        The generated collage as JPEG bytes, or None if no faces are found.
    """
    if not image_bytes_list:
        return None
    try:
        # Step 1: Extract, crop, and normalize all faces to a standard width.
        faces = _extract_and_prepare_faces(image_bytes_list, target_face_width=360)
        if not faces:
            logger.warning("No faces could be prepared from the provided images.")
            return None
        
        # Step 2: Pack the normalized faces onto the canvas, filling it completely.
        final_canvas = _pack_faces_onto_canvas(
            faces, TIKTOK_CANVAS_W, TIKTOK_CANVAS_H, TIKTOK_BG_FALLBACK_BGR
        )
        
        # Step 3: Convert the final canvas to JPEG bytes and return.
        return convert_bgr_to_jpeg_bytes(final_canvas)
    except Exception:
        logger.exception("A critical error occurred in create_portrait_collage_from_bytes.")
        return None


def split_and_stack_image_bytes(image_bytes: bytes) -> tuple[bytes | None, bytes | None]:
    """
    Split a horizontally concatenated image (front + side view) into two separate images.
    No letterbox removal here: generation must be full-bleed by prompt & collage.
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
    
    # Запасной вариант, если лицо не будет найдено
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
            
            # Добавляем отступы для эстетики
            head_height = y_max_head - y_min_head
            safe_zone['y_start'] = max(0, y_min_head - int(head_height * 0.5))
            safe_zone['y_end'] = min(h, y_max_head + int(head_height * 0.3))

    safe_zone['height'] = safe_zone['y_end'] - safe_zone['y_start']
    safe_zone['headroom'] = safe_zone['y_start']  # Пространство сверху, которое можно обрезать
    safe_zone['chinroom'] = h - safe_zone['y_end'] # Пространство снизу
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
    Интеллектуально объединяет изображения матери, отца и ребенка в один
    вертикальный портрет 9:16 с динамическим распределением высоты.
    """
    img_mom = load_image_bgr_from_bytes(img_top_bytes)
    img_dad = load_image_bgr_from_bytes(img_bottom_bytes)
    img_child = load_image_bgr_from_bytes(img_middle_bytes)

    if img_mom is None or img_dad is None or img_child is None:
        raise ValueError("Одно или несколько изображений не удалось загрузить.")

    # 1. Приведение к единой ширине
    target_width = min(img_mom.shape[1], img_dad.shape[1])
    
    def resize_to_width(img, new_width):
        h, w, _ = img.shape
        scale = new_width / w
        return cv2.resize(img, (new_width, int(h * scale)), interpolation=cv2.INTER_AREA)

    mom_resized = resize_to_width(img_mom, target_width)
    dad_resized = resize_to_width(img_dad, target_width)
    child_resized = resize_to_width(img_child, target_width // 2)
    
    # 2. Анализ безопасных зон на масштабированных изображениях
    safe_mom = _analyze_image_safe_zone(mom_resized)
    safe_dad = _analyze_image_safe_zone(dad_resized)
    safe_child = _analyze_image_safe_zone(child_resized)

    # 3. Динамическое распределение высоты
    final_width = target_width
    final_height = int(final_width * 16 / 9)

    total_safe_height = safe_mom['height'] + safe_dad['height'] + safe_child['height']
    
    # Общее пространство, доступное для обрезки
    total_croppable_space = (safe_mom['headroom'] + safe_mom['chinroom'] + 
                             safe_dad['headroom'] + safe_dad['chinroom'] + 
                             safe_child['headroom'] + safe_child['chinroom'])
    
    # Пространство, которое нужно распределить под фон
    extra_height_to_distribute = final_height - total_safe_height

    if extra_height_to_distribute < 0:
        # Критический случай: головы не помещаются. Сжимаем все пропорционально.
        scale = final_height / total_safe_height
        h_mom = int(safe_mom['height'] * scale)
        h_dad = int(safe_dad['height'] * scale)
        h_child = final_height - h_mom - h_dad
    else:
        # Распределяем дополнительное пространство пропорционально доступному для обрезки фону
        def get_share(safe_zone):
            return (safe_zone['headroom'] + safe_zone['chinroom']) / total_croppable_space if total_croppable_space > 0 else 1/3

        extra_mom = int(extra_height_to_distribute * get_share(safe_mom))
        extra_dad = int(extra_height_to_distribute * get_share(safe_dad))
        extra_child = final_height - total_safe_height - extra_mom - extra_dad

        h_mom = safe_mom['height'] + extra_mom
        h_dad = safe_dad['height'] + extra_dad
        h_child = safe_child['height'] + extra_child

    # 4. Финальная обрезка до рассчитанных высот
    mom_final = _crop_to_center_face(mom_resized, h_mom)
    dad_final = _crop_to_center_face(dad_resized, h_dad)
    child_final = _crop_to_center_face(child_resized, h_child)
    
    # 5. Сборка холста
    canvas = np.full((final_height, final_width, 3), 128, dtype=np.uint8)
    
    current_y = 0
    # Мать
    canvas[current_y : current_y + h_mom, :] = mom_final
    current_y += h_mom
    # Отец
    canvas[current_y : current_y + h_dad, :] = dad_final
    current_y += h_dad
    # Ребенок (слева внизу)
    child_h, child_w, _ = child_final.shape
    canvas[current_y : current_y + child_h, 0 : child_w] = child_final

    return convert_bgr_to_jpeg_bytes(canvas)
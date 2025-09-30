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
mp_selfie_seg = mp.solutions.selfie_segmentation


# --- Cropping parameters ---
HEAD_VERTICAL_MARGIN_RATIO = 0.40
HEAD_HORIZONTAL_MARGIN_RATIO = 0.50

# --- Fixed canvas (must NOT change) ---
TIKTOK_CANVAS_W = 1152
TIKTOK_CANVAS_H = 1024
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


    # ---------- helpers (English only) ----------

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
    # Linear-space SoG; skip if gains are near-neutral to avoid "plastic skin".
    lin = _srgb_to_linear_01(bgr)
    m = np.power(np.mean(np.power(lin, p), axis=(0, 1)) + 1e-8, 1.0 / p)
    g = float(np.mean(m))
    gains = g / (m + 1e-8)
    if (np.max(gains) - np.min(gains)) < 0.06:
        return bgr.copy()
    gains = np.clip(gains, gain_clip[0], gain_clip[1])
    return _linear_to_srgb_u8(lin * gains[None, None, :])

def _clahe_conditional(bgr: np.ndarray, clip_limit: float = 1.05, tile=(8, 8), std_thresh: float = 45.0) -> np.ndarray:
    # Apply CLAHE only when L-channel has low contrast.
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    if float(l.std()) < std_thresh:
        clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile)
        l = clahe.apply(l)
    return cv2.cvtColor(cv2.merge((l, a, b)), cv2.COLOR_LAB2BGR)

def _variance_of_laplacian(bgr: np.ndarray) -> float:
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(gray, cv2.CV_64F, ksize=3).var())

def _choose_reference_index(tiles: List[np.ndarray]) -> int:
    best_idx, best_score = 0, -1e9
    for i, t in enumerate(tiles):
        sharp = _variance_of_laplacian(t)
        mean = float(cv2.cvtColor(t, cv2.COLOR_BGR2GRAY).mean())
        brightness_bonus = 1.0 - abs(mean - 128.0) / 128.0
        score = 0.8 * sharp + 0.2 * (1000.0 * brightness_bonus)
        if score > best_score:
            best_score, best_idx = score, i
    return best_idx

def _center_crop_to_aspect(bgr: np.ndarray, aspect: float) -> np.ndarray:
    h, w = bgr.shape[:2]
    ar = w / float(h)
    if ar > aspect:
        new_w = int(round(h * aspect))
        x1 = max(0, (w - new_w) // 2)
        return bgr[:, x1:x1 + new_w]
    else:
        new_h = int(round(w / aspect))
        y1 = max(0, (h - new_h) // 2 - int(0.05 * h))  # slight upward bias
        y1 = max(0, min(y1, h - new_h))
        return bgr[y1:y1 + new_h, :]

def _crop_around_face(bgr: np.ndarray, aspect: float) -> np.ndarray:
    h, w = bgr.shape[:2]
    with mp_face_detection.FaceDetection(model_selection=1, min_detection_confidence=0.35) as fd:
        res = fd.process(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
    bbox = None
    if res and res.detections:
        best, best_area = None, -1.0
        for det in res.detections:
            r = det.location_data.relative_bounding_box
            xa = max(0.0, r.xmin) * w
            ya = max(0.0, r.ymin) * h
            wa = max(1.0, r.width * w)
            ha = max(1.0, r.height * h)
            area = wa * ha
            if area > best_area:
                best_area, best = area, (xa, ya, wa, ha)
        bbox = best
    if bbox is None:
        return _center_crop_to_aspect(bgr, aspect)
    x, y, bw, bh = bbox
    cx, cy = x + bw / 2.0, y + bh / 2.0
    s = max(bw, bh) * 2.4  # cover head+shoulders
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

def _skin_mask_ycrcb(bgr: np.ndarray) -> np.ndarray:
    # Conservative skin mask in YCrCb; output [0..1]
    ycrcb = cv2.cvtColor(bgr, cv2.COLOR_BGR2YCrCb)
    skin = cv2.inRange(ycrcb, (0, 133, 77), (255, 173, 127))
    skin = cv2.medianBlur(skin, 5)
    skin = cv2.morphologyEx(skin, cv2.MORPH_CLOSE, np.ones((3,3), np.uint8), iterations=1)
    return (skin.astype(np.float32) / 255.0)

def _person_alpha_mask_improved(bgr: np.ndarray, t_fg=0.92, t_bg=0.18, feather_px=6) -> np.ndarray:
    # Selfie segmentation + distance transform alpha + bilateral smoothing.
    h, w = bgr.shape[:2]
    with mp.solutions.selfie_segmentation.SelfieSegmentation(model_selection=1) as seg:
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
    alpha = cv2.GaussianBlur(alpha_bi, (0, 0), sigmaX=max(3, feather_px)/3.0, sigmaY=max(3, feather_px)/3.0)
    return np.clip(alpha, 0.0, 1.0)

def _composite_on_gray_improved(bgr: np.ndarray, bg=(190, 190, 190)) -> np.ndarray:
    a = _person_alpha_mask_improved(bgr)[:, :, None]
    bg_img = np.full_like(bgr, bg, dtype=np.uint8)
    comp = (a * bgr.astype(np.float32) + (1.0 - a) * bg_img.astype(np.float32)).astype(np.uint8)
    return comp

def _reinhard_color_transfer_masked(src_bgr: np.ndarray, ref_bgr: np.ndarray,
                                    src_mask: Optional[np.ndarray] = None,
                                    ref_mask: Optional[np.ndarray] = None,
                                    alpha: float = 0.40) -> np.ndarray:
    # Restrict stats to SKIN within PERSON.
    if src_mask is not None:
        src_mask = np.clip(src_mask * _skin_mask_ycrcb(src_bgr), 0.0, 1.0)
    if ref_mask is not None:
        ref_mask = np.clip(ref_mask * _skin_mask_ycrcb(ref_bgr), 0.0, 1.0)

    def _stats_lab(bgr, mask):
        lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB).astype(np.float32)
        if mask is None:
            mean = np.array([lab[..., i].mean() for i in range(3)], np.float32)
            std  = np.array([lab[..., i].std()  for i in range(3)], np.float32)
            return lab, mean, std
        w = np.clip(mask.astype(np.float32), 0.0, 1.0)
        w3 = np.dstack([w, w, w]); tot = w.sum() + 1e-6
        mean = (lab * w3).reshape(-1, 3).sum(0) / tot
        std  = np.sqrt((((lab - mean) * w3) ** 2).reshape(-1, 3).sum(0) / tot + 1e-6)
        return lab, mean, std

    src_lab, sm, ss = _stats_lab(src_bgr, src_mask)
    ref_lab, rm, rs = _stats_lab(ref_bgr, ref_mask)
    out = np.empty_like(src_lab)
    for i in range(3):
        ch = src_lab[..., i]
        ch = (ch - sm[i]) / (ss[i] if ss[i] > 1e-6 else 1.0)
        ch = ch * (rs[i] if rs[i] > 1e-6 else 1.0) + rm[i]
        out[..., i] = ch
    out = np.clip(out, 0, 255).astype(np.uint8)
    out_bgr = cv2.cvtColor(out, cv2.COLOR_LAB2BGR)
    return cv2.addWeighted(out_bgr, alpha, src_bgr, 1.0 - alpha, 0.0)

def _usm(bgr: np.ndarray, amount: float = 0.45, radius: float = 0.7, thresh: int = 3) -> np.ndarray:
    blur = cv2.GaussianBlur(bgr, (0, 0), radius)
    mask = cv2.subtract(bgr, blur)
    gray = cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY)
    mask[gray < thresh] = 0
    return cv2.addWeighted(bgr, 1.0, mask, amount, 0)

# --------------- Public API ---------------

def create_portrait_collage_from_bytes(image_bytes_list: List[bytes]) -> Optional[bytes]:
    """
    Build ONE 2x2 portrait collage (1152x1024, AR 9:8) from exactly 4 images.
    Pipeline:
      1) Linear-sRGB Shades-of-Gray WB (soft, clipped, auto-skip if near-neutral),
      2) Face crop to 9:8 via MediaPipe FaceDetection (head-and-shoulders),
      3) Conditional CLAHE (very light) in Lab,
      4) Resize tiles to 576x512,
      5) Choose a reference tile by sharpness (variance of Laplacian),
      6) Reinhard color transfer to reference on SKIN-within-PERSON mask (alpha=0.40),
      7) Selfie Segmentation + distance-transform alpha + bilateral smoothing; gray BG (190,190,190),
      8) Light Unsharp Mask (recover micro-textures),
      9) Assemble 2x2 collage and return JPEG bytes.
    """

    # ---------- pipeline ----------

    if not image_bytes_list or len(image_bytes_list) != 4:
        logger.warning("Exactly 4 images are required.")
        return None

    try:
        canvas_w, canvas_h = TIKTOK_CANVAS_W, TIKTOK_CANVAS_H   # 1152x1024
        tile_w, tile_h = canvas_w // 2, canvas_h // 2           # 576x512
        target_aspect = float(tile_w) / float(tile_h)           # 9/8

        pre_tiles: List[np.ndarray] = []
        pre_masks: List[np.ndarray] = []

        for data in image_bytes_list:
            img = load_image_bgr_from_bytes(data)
            if img is None:
                pre_tiles.append(np.full((tile_h, tile_w, 3), (190, 190, 190), dtype=np.uint8))
                pre_masks.append(np.ones((tile_h, tile_w), dtype=np.float32))
                continue

            # WB (soft, auto-skip if near-neutral)
            img = _shades_of_gray_cc_linear(img, p=4, gain_clip=(0.90, 1.10))

            # Crop to aspect around the face
            crop = _crop_around_face(img, target_aspect)

            # Light, conditional CLAHE
            crop = _clahe_conditional(crop, clip_limit=1.05, tile=(8, 8), std_thresh=45.0)

            # Resize to tile size
            tile = _resize_smart(crop, tile_w, tile_h)

            # Person mask for later color transfer and background replacement
            person_mask = _person_alpha_mask_improved(tile, t_fg=0.92, t_bg=0.18, feather_px=6)

            pre_tiles.append(tile)
            pre_masks.append(person_mask)

        # Choose the reference tile
        ref_idx = _choose_reference_index(pre_tiles)
        ref_tile = pre_tiles[ref_idx]
        ref_mask = pre_masks[ref_idx]

        # Color transfer to reference (only on skin within person), alpha=0.40
        tiles_color = []
        for i, t in enumerate(pre_tiles):
            if i == ref_idx:
                tiles_color.append(t)
            else:
                tiles_color.append(
                    _reinhard_color_transfer_masked(t, ref_tile, pre_masks[i], ref_mask, alpha=0.40)
                )

        # Composite on neutral gray and apply light USM
        tiles_comp = []
        for t in tiles_color:
            comp = _composite_on_gray_improved(t, bg=(190, 190, 190))
            comp = _usm(comp, amount=0.45, radius=0.7, thresh=3)
            tiles_comp.append(comp)

        # Assemble 2x2 collage
        canvas = np.full((canvas_h, canvas_w, 3), (190, 190, 190), dtype=np.uint8)
        canvas[0:tile_h, 0:tile_w] = tiles_comp[0]
        canvas[0:tile_h, tile_w:canvas_w] = tiles_comp[1]
        canvas[tile_h:canvas_h, 0:tile_w] = tiles_comp[2]
        canvas[tile_h:canvas_h, tile_w:canvas_w] = tiles_comp[3]

        return convert_bgr_to_jpeg_bytes(canvas, quality=95)

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
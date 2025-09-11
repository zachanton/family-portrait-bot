# aiogram_bot_template/services/photo_processing.py
import cv2
import io
import mediapipe as mp
import numpy as np
import structlog
from typing import Optional, Tuple
from PIL import Image, ImageOps
from dataclasses import dataclass

logger = structlog.get_logger(__name__)

# ------------------------------
# Public dataclass (оставил, если где-то используется)
# ------------------------------
@dataclass
class ProcessedImageOutput:
    headshot: bytes
    portrait: bytes
    half_body: bytes

# ------------------------------
# Mediapipe: ключевые индексы landmark'ов
# ------------------------------
RIGHT_EYE_OUTER = 33
LEFT_EYE_OUTER  = 263
CHIN_BOTTOM     = 152
FOREHEAD_TOP    = 10

# Таргеты для разных кропов:
# (доля высоты головы от высоты кадра, верхний отступ лба от верха кадра)
CROP_PARAMS = {
    "headshot":  (0.65, 0.15),
    "portrait":  (0.50, 0.20),
    "half_body": (0.37, 0.18),
}

# ------------------------------
# I/O utils
# ------------------------------
def load_image_bgr_from_bytes(data: bytes) -> Optional[np.ndarray]:
    try:
        img = Image.open(io.BytesIO(data))
        img = ImageOps.exif_transpose(img)
        return cv2.cvtColor(np.asarray(img.convert("RGB")), cv2.COLOR_RGB2BGR)
    except Exception:
        logger.exception("Failed to load image from bytes")
        return None

def convert_bgr_to_jpeg_bytes(img_bgr: np.ndarray, quality: int = 90) -> bytes:
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    buf = io.BytesIO()
    Image.fromarray(img_rgb).save(buf, format="JPEG", quality=quality, optimize=True)
    return buf.getvalue()

# ------------------------------
# Landmark detection
# ------------------------------
def detect_face_landmarks(img_bgr: np.ndarray) -> np.ndarray:
    h, w = img_bgr.shape[:2]
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    with mp.solutions.face_mesh.FaceMesh(
        static_image_mode=True,
        max_num_faces=1,
        refine_landmarks=True,
        min_detection_confidence=0.5,
    ) as fm:
        res = fm.process(img_rgb)
    if not res.multi_face_landmarks:
        raise RuntimeError("Face landmarks not found")
    lmk = res.multi_face_landmarks[0].landmark
    return np.array([(p.x * w, p.y * h) for p in lmk], dtype=np.float32)

# ------------------------------
# Выравнивание и кроп БЕЗ вырезки
# ------------------------------
def align_and_crop_robust(
    img_bgr: np.ndarray,
    lmk_px: np.ndarray,
    out_wh: Tuple[int, int] = (1536, 1920),
    crop_mode: str = "half_body",
    center_shift_x: float = 0.0,  # [-0.3..0.3] смещаем голову внутри кадра
) -> np.ndarray:
    """
    Делает портретный кроп с выравниванием по глазам и масштабом по высоте головы.
    Никаких масок; фон остаётся исходным.
    center_shift_x: отрицательно — левее (для левой персоны), положительно — правее.
    """
    W, H = out_wh
    t_head_frac, top_margin_frac = CROP_PARAMS.get(crop_mode, CROP_PARAMS["portrait"])

    p_re = lmk_px[RIGHT_EYE_OUTER]
    p_le = lmk_px[LEFT_EYE_OUTER]
    p_ch = lmk_px[CHIN_BOTTOM]
    p_fr = lmk_px[FOREHEAD_TOP]

    # угол по линии глаз
    d = p_le - p_re
    angle_deg = float(np.degrees(np.arctan2(d[1], d[0])))

    # центр/масштаб по высоте головы
    head_center = (p_ch + p_fr) / 2.0
    head_h = max(1.0, float(np.linalg.norm(p_ch - p_fr)))
    target_head_h = H * t_head_frac
    scale = target_head_h / head_h

    # базовая матрица: вращение + масштаб вокруг центра головы
    M = cv2.getRotationMatrix2D(tuple(head_center), angle_deg, scale)

    # вертикально: ставим лоб на top_margin
    tr_fr = np.dot(M, np.array([p_fr[0], p_fr[1], 1.0]))
    target_y = H * top_margin_frac
    M[1, 2] += target_y - tr_fr[1]

    # горизонт: центр головы смещаем к нужной позиции
    tr_center = np.dot(M, np.array([head_center[0], head_center[1], 1.0]))
    target_x = (W * 0.5) + (center_shift_x * W)
    M[0, 2] += target_x - tr_center[0]

    # ВАЖНО: не REFLECT — берём REPLICATE, чтобы не появлялись «лишние руки»
    out = cv2.warpAffine(
        img_bgr, M, (W, H),
        flags=cv2.INTER_LANCZOS4,
        borderMode=cv2.BORDER_REPLICATE
    )
    return out

# ------------------------------
# ПРОСТОЕ объединение «плечо к плечу»
# ------------------------------
def create_simple_side_by_side(
    person1_bytes: bytes,
    person2_bytes: bytes,
    per_person_wh: Tuple[int, int] = (1536, 1920),  # портрет каждого
    shoulder_shift: float = 0.14,                   # сдвиг головы внутрь кадра для «контакта»
) -> bytes:
    """
    Никакой сегментации. Делаем два выровненных кропа и склеиваем по горизонтали.
    Если half_body сделать не получается, используем portrait.
    """
    p1 = load_image_bgr_from_bytes(person1_bytes)
    p2 = load_image_bgr_from_bytes(person2_bytes)
    if p1 is None or p2 is None:
        logger.error("Failed to load one of the images.")
        return person1_bytes or person2_bytes

    Wp, Hp = per_person_wh

    def crop_best(img, side_left: bool):
        try:
            lmk = detect_face_landmarks(img)
            # пробуем half_body
            shift = (-shoulder_shift if side_left else shoulder_shift)
            crop = align_and_crop_robust(img, lmk, out_wh=(Wp, Hp), crop_mode="half_body", center_shift_x=shift)
            return crop
        except Exception:
            logger.exception("Half-body crop failed, falling back to portrait.")
            try:
                lmk = detect_face_landmarks(img)
                shift = (-shoulder_shift if side_left else shoulder_shift)
                return align_and_crop_robust(img, lmk, out_wh=(Wp, Hp), crop_mode="portrait", center_shift_x=shift)
            except Exception:
                # крайний фолбэк — просто центрируем оригинал
                return cv2.resize(img, (Wp, Hp), interpolation=cv2.INTER_LANCZOS4)

    left  = crop_best(p1, side_left=True)
    right = crop_best(p2, side_left=False)

    # Склейка без зазора — плечи визуально «сходятся» за счёт сдвига головы внутрь
    final = cv2.hconcat([left, right])
    return convert_bgr_to_jpeg_bytes(final, quality=92)

# ------------------------------
# Публичная точка входа
# ------------------------------
def create_composite_image(person1_bytes: bytes, person2_bytes: bytes) -> bytes:
    logger.info("Creating simple side-by-side composite...")
    try:
        # итог: два портретa 1536×1920 => общий 3072×1920
        return create_simple_side_by_side(person1_bytes, person2_bytes, per_person_wh=(1536, 1920), shoulder_shift=0.14)
    except Exception:
        logger.exception("Simple side-by-side failed, falling back to naive concat.")
        p1 = load_image_bgr_from_bytes(person1_bytes)
        p2 = load_image_bgr_from_bytes(person2_bytes)
        if p1 is not None and p2 is not None:
            H = 1920
            left  = cv2.resize(p1, (1536, H), interpolation=cv2.INTER_LANCZOS4)
            right = cv2.resize(p2, (1536, H), interpolation=cv2.INTER_LANCZOS4)
            return convert_bgr_to_jpeg_bytes(cv2.hconcat([left, right]))
        return person1_bytes or person2_bytes

# ------------------------------
# Доп. API (если где-то использовалось)
# ------------------------------
def preprocess_image(image_bytes: bytes) -> Optional[ProcessedImageOutput]:
    """
    Оставил прежний интерфейс: делаем три квадратных кропа 1024×1024.
    """
    img_bgr = load_image_bgr_from_bytes(image_bytes)
    if img_bgr is None:
        return None
    try:
        lmk = detect_face_landmarks(img_bgr)
        def sq(crop_mode):
            return align_and_crop_robust(img_bgr, lmk, out_wh=(1024, 1024), crop_mode=crop_mode, center_shift_x=0.0)
        headshot = convert_bgr_to_jpeg_bytes(sq("headshot"))
        portrait = convert_bgr_to_jpeg_bytes(sq("portrait"))
        half_body = convert_bgr_to_jpeg_bytes(sq("half_body"))
        return ProcessedImageOutput(headshot=headshot, portrait=portrait, half_body=half_body)
    except Exception:
        logger.exception("Preprocessing pipeline failed.")
        return None

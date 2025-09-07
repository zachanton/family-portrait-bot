# aiogram_bot_template/services/photo_processing.py
import io
import math
from typing import Tuple, Optional, Dict, Any

import cv2
import mediapipe as mp
import numpy as np
import structlog
from PIL import Image, ImageOps

logger = structlog.get_logger(__name__)

# Initialize MediaPipe solutions once
mp_face_detection = mp.solutions.face_detection
mp_selfie_segmentation = mp.solutions.selfie_segmentation


# ------------------------------
# I/O helpers
# ------------------------------
def load_image_bgr_from_bytes(data: bytes) -> Optional[np.ndarray]:
    """Load image from bytes, auto-rotate from EXIF, return as BGR uint8."""
    try:
        img = Image.open(io.BytesIO(data))
        img = ImageOps.exif_transpose(img)  # rotate & clear EXIF Orientation
        img = img.convert("RGB")
        arr = np.asarray(img)
        return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
    except Exception:
        logger.exception("Failed to load image from bytes")
        return None


def convert_bgr_to_jpeg_bytes(img_bgr: np.ndarray, quality: int = 90) -> bytes:
    """Converts a BGR NumPy array to JPEG bytes."""
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    pil_img = Image.fromarray(img_rgb)
    buffer = io.BytesIO()
    pil_img.save(buffer, format="JPEG", quality=quality, optimize=True)
    return buffer.getvalue()


# ------------------------------
# Face detection & alignment
# ------------------------------
def detect_face_and_eyes_bgr(img_bgr: np.ndarray, conf: float = 0.5) -> Optional[Dict[str, Any]]:
    """Return first face bbox + left/right eye pixel coords or None."""
    h, w = img_bgr.shape[:2]
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    with mp_face_detection.FaceDetection(model_selection=1, min_detection_confidence=conf) as fd:
        res = fd.process(img_rgb)
    if not res.detections:
        return None
    det = res.detections[0]
    kp = det.location_data.relative_keypoints
    right_eye = (int(kp[0].x * w), int(kp[0].y * h))
    left_eye  = (int(kp[1].x * w), int(kp[1].y * h))
    rb = det.location_data.relative_bounding_box
    bbox = (int(rb.xmin * w), int(rb.ymin * h), int(rb.width * w), int(rb.height * h))
    return {"left_eye": left_eye, "right_eye": right_eye, "bbox": bbox}


def _guided_filter_safe(src: np.ndarray, guide_gray_01: np.ndarray) -> np.ndarray:
    """Edge-aware smoothing for masks if ximgproc is available."""
    try:
        import cv2.ximgproc as xip  # type: ignore
        out = xip.guidedFilter(guide=guide_gray_01, src=src.astype(np.float32), radius=10, eps=1e-6)
        return np.clip(out, 0.0, 1.0).astype(np.float32)
    except Exception:
        return cv2.blur(src.astype(np.float32), (3, 3)).astype(np.float32)


def align_and_crop_head_shoulders(img_bgr: np.ndarray) -> np.ndarray:
    """
    Align by eyes, scale, and crop to a portrait window while keeping hair & chin/shoulders.
    Returns a BGR crop (not yet resized to canvas).
    """
    info = detect_face_and_eyes_bgr(img_bgr)
    if not info:
        logger.warning("No face detected for alignment, using center crop as fallback.")
        h, w = img_bgr.shape[:2]
        side = min(h, w)
        sx = (w - side) // 2
        sy = (h - side) // 2
        return img_bgr[sy: sy + side, sx: sx + side]

    le = np.array(info["left_eye"], dtype=np.float32)
    re = np.array(info["right_eye"], dtype=np.float32)
    eyes_c = (le + re) / 2.0
    dy, dx = le[1] - re[1], le[0] - re[0]
    angle = math.degrees(math.atan2(dy, dx))

    # Rotate to make eyes horizontal
    M = cv2.getRotationMatrix2D(tuple(eyes_c), -angle, 1.0)
    rotated = cv2.warpAffine(
        img_bgr, M, (img_bgr.shape[1], img_bgr.shape[0]),
        flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE
    )

    io = float(np.linalg.norm(le - re))
    if io < 1.0:
        return rotated

    # Slight zoom-out by default to avoid tight crops on hair/chin
    desired_io = 135.0
    scale = desired_io / io
    scaled = cv2.resize(
        rotated,
        (int(round(rotated.shape[1] * scale)), int(round(rotated.shape[0] * scale))),
        interpolation=cv2.INTER_LANCZOS4
    )
    eyes_c_s = eyes_c * scale

    # Wider/taller crop to keep hair & chin. 4:5-ish portrait.
    crop_w = int(round(desired_io * 3.2))           # was 3.0 — добавили ширины под волосы
    crop_h = int(round(crop_w * 1.30))              # было 1.25 — добавили низа под подбородок

    # Initial placement: more space above eyes but also enough below
    x1 = int(round(eyes_c_s[0] - crop_w / 2))
    y1 = int(round(eyes_c_s[1] - crop_h * 0.56))    # было 0.60 → ниже, чтобы сохранить подбородок
    x2 = x1 + crop_w
    y2 = y1 + crop_h

    try:
        # Person mask to adjust top (hair/hat) and bottom (chin/shoulders)
        mask = segment_person(scaled)
        if mask is not None:
            H, W = scaled.shape[:2]
            cx = int(round(eyes_c_s[0]))
            strip_half = max(12, int(round(crop_w * 0.35)))
            xL = max(0, cx - strip_half)
            xR = min(W, cx + strip_half)
            col = np.max(mask[:, xL:xR], axis=1)  # [H]

            ys = np.where(col > 0.35)[0]
            if ys.size > 0:
                top_person = int(ys[0])
                bot_person = int(ys[-1])

                # 1) Keep at least 10% crop_h above hair/hat
                top_margin = int(round(0.10 * crop_h))
                target_y1 = max(0, top_person - top_margin)
                if target_y1 < y1:
                    delta = y1 - target_y1
                    y1 -= delta
                    y2 -= delta

                # 2) Keep at least 18% crop_h below bottom (chin/shoulders safety)
                bottom_margin = int(round(0.18 * crop_h))
                target_y2 = min(H, bot_person + bottom_margin)
                if target_y2 > y2:
                    delta = target_y2 - y2
                    y1 += delta
                    y2 += delta

            # 3) Additional geometric guard for chin:
            # from eyes to chin ~ 1.15 * IO — гарантируем, что низ ниже этой точки.
            min_bottom = int(round(eyes_c_s[1] + 1.15 * desired_io))
            if y2 < min_bottom:
                shift = min_bottom - y2
                y1 += shift
                y2 += shift

            # 4) Auto zoom-out if touching edges after adjustments
            touch_top = y1 <= 2
            touch_bottom = y2 >= H - 2
            if touch_top or touch_bottom:
                shrink = 0.9  # zoom out by 10%
                new_w = max(1, int(round(scaled.shape[1] * shrink)))
                new_h = max(1, int(round(scaled.shape[0] * shrink)))
                scaled = cv2.resize(scaled, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)
                mask = cv2.resize(mask, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
                eyes_c_s *= shrink
                crop_w = int(round(crop_w * shrink))
                crop_h = int(round(crop_h * shrink))
                x1 = int(round(eyes_c_s[0] - crop_w / 2))
                y1 = int(round(eyes_c_s[1] - crop_h * 0.56))
                x2 = x1 + crop_w
                y2 = y1 + crop_h
    except Exception:
        pass

    # Pad if out of bounds
    H, W = scaled.shape[:2]
    pad_l = max(0, -x1)
    pad_t = max(0, -y1)
    pad_r = max(0, x2 - W)
    pad_b = max(0, y2 - H)
    if any((pad_l, pad_t, pad_r, pad_b)):
        scaled = cv2.copyMakeBorder(
            scaled, pad_t, pad_b, pad_l, pad_r, cv2.BORDER_REPLICATE
        )
        x1 += pad_l; x2 += pad_l
        y1 += pad_t; y2 += pad_t

    crop = scaled[y1:y2, x1:x2].copy()
    return crop


# ------------------------------
# Color normalization
# ------------------------------
def color_normalize(img_bgr: np.ndarray) -> np.ndarray:
    """Robust gray-world white balance + gentle CLAHE on L channel (LAB)."""
    # Gray-world WB (safe numpy version)
    img = img_bgr.astype(np.float32) + 1e-6
    avg_b, avg_g, avg_r = img.reshape(-1, 3).mean(axis=0)
    avg = (avg_b + avg_g + avg_r) / 3.0
    img[..., 0] *= (avg / avg_b)
    img[..., 1] *= (avg / avg_g)
    img[..., 2] *= (avg / avg_r)
    img = np.clip(img, 0, 255).astype(np.uint8)

    # CLAHE on L channel (softer settings to avoid over-contrast on skin)
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=1.6, tileGridSize=(12, 12))
    l2 = clahe.apply(l)
    lab2 = cv2.merge((l2, a, b))
    return cv2.cvtColor(lab2, cv2.COLOR_LAB2BGR)


# ------------------------------
# Person segmentation & background
# ------------------------------
def _fill_holes(binary_mask: np.ndarray) -> np.ndarray:
    """
    Fill holes in a binary mask (uint8 0/255) via flood-fill from borders.
    Returns binary mask uint8 0/255 with filled holes.
    """
    h, w = binary_mask.shape[:2]
    inv = 255 - binary_mask
    mask = np.zeros((h + 2, w + 2), np.uint8)
    flood = inv.copy()
    cv2.floodFill(flood, mask, (0, 0), 128)
    flood[flood == 255] = 0
    flood[flood == 128] = 255
    filled_inv = flood
    filled = 255 - filled_inv
    return filled


def segment_person(img_bgr: np.ndarray) -> Optional[np.ndarray]:
    """
    Create a soft segmentation mask for the person in [0..1], refined for hair & shoulders.
    Uses adaptive model_selection and guided filtering (if available).
    """
    h, w = img_bgr.shape[:2]

    # Choose model by estimated face size (close-up vs far)
    face = detect_face_and_eyes_bgr(img_bgr)
    model_sel = 0
    if face and "bbox" in face:
        _, _, bw, bh = face["bbox"]
        ratio = max(bw / float(w), bh / float(h))
        model_sel = 0 if ratio >= 0.18 else 1

    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    with mp_selfie_segmentation.SelfieSegmentation(model_selection=model_sel) as seg:
        res = seg.process(img_rgb)
    if res.segmentation_mask is None:
        return None
    mask = res.segmentation_mask.astype(np.float32)

    # Preserve hair: light dilation + gaussian feather
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    mask = cv2.dilate(mask, k, iterations=1)
    mask = cv2.GaussianBlur(mask, (5, 5), 0)

    # Edge-aware refinement if possible
    guide = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
    mask = _guided_filter_safe(mask, guide)

    # Solid foreground to remove small holes (hands/torso artifacts)
    bin_fg = (mask > 0.55).astype(np.uint8) * 255
    bin_fg = cv2.morphologyEx(bin_fg, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8), iterations=1)
    bin_fg = _fill_holes(bin_fg)

    solid = (bin_fg > 127).astype(np.float32)
    matte = np.maximum(mask, solid * 0.98)  # interior fully opaque
    return np.clip(matte, 0.0, 1.0).astype(np.float32)


def add_neutral_background(img_bgr: np.ndarray, bg_color: Tuple[int, int, int] = (230, 230, 230)) -> np.ndarray:
    """
    Replace background with a neutral color using refined segmentation mask.
    Performs linear-light alpha composite to avoid gray halos around hair.
    Skips replacement if mask is unreliable (covers almost the whole frame).
    """
    mask = segment_person(img_bgr)
    if mask is None:
        return img_bgr

    coverage = float(np.mean(mask > 0.5))
    if coverage > 0.95:
        return img_bgr

    # Slightly favor hair boundary
    mask = np.clip(mask * 1.05, 0.0, 1.0).astype(np.float32)

    fg = img_bgr.astype(np.float32) / 255.0
    bg = (np.full(img_bgr.shape, bg_color, dtype=np.float32) / 255.0)

    # Composite in (approx) linear space to avoid halos
    fg_lin = np.power(fg, 2.2)
    bg_lin = np.power(bg, 2.2)
    m3 = np.dstack([mask, mask, mask]).astype(np.float32)

    out_lin = fg_lin * m3 + bg_lin * (1.0 - m3)
    out = np.power(np.clip(out_lin, 0.0, 1.0), 1.0 / 2.2)
    return (out * 255.0 + 0.5).astype(np.uint8)


# ------------------------------
# Canvas fitting
# ------------------------------
def fit_to_canvas(img_bgr: np.ndarray, size: int = 1024, bg_color: Tuple[int, int, int] = (230, 230, 230)) -> np.ndarray:
    """Fit image onto a square canvas with letterboxing."""
    h, w = img_bgr.shape[:2]
    scale = min(size / w, size / h)
    new_w, new_h = int(round(w * scale)), int(round(h * scale))
    resized = cv2.resize(img_bgr, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)

    canvas = np.full((size, size, 3), bg_color, dtype=np.uint8)
    x_offset = (size - new_w) // 2
    y_offset = (size - new_h) // 2
    canvas[y_offset:y_offset + new_h, x_offset:x_offset + new_w] = resized
    return canvas


# ------------------------------
# End-to-end pipeline
# ------------------------------
def preprocess_image(image_bytes: bytes) -> Optional[bytes]:
    """
    Full preprocessing pipeline for a single portrait image.
    Returns: Processed image as JPEG bytes, or None if processing fails.
    """
    logger.info("Starting image preprocessing pipeline...")

    img = load_image_bgr_from_bytes(image_bytes)
    if img is None:
        return None
    logger.debug("Image loaded successfully.", width=img.shape[1], height=img.shape[0])

    aligned_crop = align_and_crop_head_shoulders(img)
    logger.debug("Face aligned and cropped.", crop_w=aligned_crop.shape[1], crop_h=aligned_crop.shape[0])

    color_corrected = color_normalize(aligned_crop)
    logger.debug("Color corrected.")

    with_bg = add_neutral_background(color_corrected)
    logger.debug("Neutral background added.")

    final_canvas = fit_to_canvas(with_bg, size=1024)
    logger.debug("Fitted to final canvas.", canvas_size=1024)

    output_bytes = convert_bgr_to_jpeg_bytes(final_canvas)
    logger.info("Image preprocessing finished.", final_size_kb=len(output_bytes) / 1024.0)

    return output_bytes

# aiogram_bot_template/services/face_processor.py
# CPU-only, single-image preprocessing tuned so any processed photo will match any other.
# Public API preserved:
#   detect_and_crop_face(image_bytes: bytes, padding_px: int = 300)
#       -> tuple[FaceDetectionResult, bytes | None]

from __future__ import annotations
import io
import os
import math
import urllib.request
from pathlib import Path
from typing import Literal, Tuple, Optional

import cv2
import numpy as np
from PIL import Image, ImageOps

FaceDetectionResult = Literal["SUCCESS", "NO_FACE", "MULTIPLE_FACES"]

# ------------ Config ------------
_OUTPUT_LONG_SIDE = int(os.environ.get("PORTRAIT_LONG_SIDE", "2048"))  # final vertical 4:5 long side
_TARGET_FACE_FRAC = float(os.environ.get("PORTRAIT_FACE_FRACTION", "0.34"))  # ≈34% face height fraction
_EDGE_PENALTY_LAMBDA = float(os.environ.get("PORTRAIT_EDGE_PENALTY", "0.28"))
_MAX_UNIFORM_TRIM = float(os.environ.get("PORTRAIT_MAX_TRIM", "0.035"))

# ------------ YuNet model (CPU) ------------
_YUNET_URL = "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"
_MODEL_DIR = Path(os.environ.get("YUNET_MODEL_DIR", Path.home() / ".cache" / "yunet"))
_MODEL_PATH = _MODEL_DIR / "face_detection_yunet_2023mar.onnx"
_DETECTOR: Optional[cv2.FaceDetectorYN] = None

def _ensure_model() -> Path:
    _MODEL_DIR.mkdir(parents=True, exist_ok=True)
    if not _MODEL_PATH.exists():
        print(f"Downloading YuNet model to {_MODEL_PATH}...")
        tmp = _MODEL_PATH.with_suffix(".tmp")
        try:
            req = urllib.request.Request(_YUNET_URL, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req) as r, open(tmp, "wb") as f:
                f.write(r.read())
            tmp.replace(_MODEL_PATH)
            print("Download complete.")
        except Exception as e:
            if tmp.exists():
                tmp.unlink(missing_ok=True)
            raise RuntimeError(f"Failed to download YuNet model: {e}")
    return _MODEL_PATH

def _get_detector(input_size: Tuple[int, int], score_threshold: float = 0.9) -> cv2.FaceDetectorYN:
    global _DETECTOR
    model_path = str(_ensure_model())
    if _DETECTOR is None:
        _DETECTOR = cv2.FaceDetectorYN.create(
            model=model_path,
            config="",
            input_size=(320, 320),
            score_threshold=score_threshold,
            nms_threshold=0.3,
            top_k=5000,
        )
    _DETECTOR.setInputSize(input_size)
    try:
        _DETECTOR.setScoreThreshold(score_threshold)
    except Exception:
        pass
    return _DETECTOR

# ------------ I/O + EXIF ------------
def _read_bgr_with_exif(image_bytes: bytes) -> np.ndarray:
    pil = Image.open(io.BytesIO(image_bytes))
    pil = ImageOps.exif_transpose(pil)
    rgb = np.asarray(pil.convert("RGB"))
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)

# ------------ Geometry & alignment ------------
def _compute_eye_angle_and_center(face_row: np.ndarray) -> Tuple[float, Tuple[float, float]]:
    # YuNet row: [x,y,w,h,lx,ly,rx,ry,nx,ny,lmx,lmy,rmx,rmy,score]
    lx, ly, rx, ry = float(face_row[4]), float(face_row[5]), float(face_row[6]), float(face_row[7])
    angle = math.degrees(math.atan2(ry - ly, rx - lx))
    return angle, ((lx + rx) / 2.0, (ly + ry) / 2.0)

def _rotate_box(x: float, y: float, w: float, h: float, angle_deg: float, center: Tuple[float, float]):
    M = cv2.getRotationMatrix2D(center, angle_deg, 1.0)
    pts = np.array([[x, y], [x + w, y], [x + w, y + h], [x, y + h]], dtype=np.float32)
    ones = np.ones((4, 1), dtype=np.float32)
    rot = (M @ np.hstack([pts, ones]).T).T
    x1, y1 = rot.min(axis=0); x2, y2 = rot.max(axis=0)
    return float(x1), float(y1), float(x2 - x1), float(y2 - y1)

# ------------ Skin / texture helpers ------------
def _skin_mask(rgb: np.ndarray) -> np.ndarray:
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    m1 = cv2.inRange(hsv, (0, 30, 40), (25, 200, 255))
    m2 = cv2.inRange(hsv, (160, 20, 40), (179, 200, 255))
    m = cv2.bitwise_or(m1, m2)
    k = max(1, int(min(rgb.shape[:2]) * 0.01))
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, kernel, 1)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, kernel, 1)
    return (m > 0)

def _grad_mag(gray: np.ndarray) -> np.ndarray:
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    return cv2.magnitude(gx, gy)

def _edge_low_texture_penalty(grad_small: np.ndarray, xs1: int, ys1: int, xs2: int, ys2: int) -> float:
    # Penalize low-texture left/right strips and top/bottom bands (phones, mirrors, rotation fill)
    eps = 1e-6
    g = grad_small[ys1:ys2, xs1:xs2]
    if g.size == 0:
        return 0.0
    g_all = float(np.mean(g)) + eps
    w = max(1, xs2 - xs1); h = max(1, ys2 - ys1)
    strip_w = max(1, int(round(0.15 * w)))
    band_h = max(1, int(round(0.12 * h)))
    left = float(np.mean(g[:, :strip_w])) if strip_w < w else g_all
    right = float(np.mean(g[:, -strip_w:])) if strip_w < w else g_all
    top = float(np.mean(g[:band_h, :]))
    bottom = float(np.mean(g[-band_h:, :]))
    edge_pen = max(0.0, (0.75 * g_all - min(left, right)) / g_all)
    corner_pen = max(0.0, (0.70 * g_all - min(top, bottom)) / g_all)
    return float(0.6 * edge_pen + 0.4 * corner_pen)

# ------------ Color / tone ------------
def _shades_of_gray_wb(img_rgb: np.ndarray, p: float = 6.0, gain_min: float = 0.92, gain_max: float = 1.08) -> np.ndarray:
    I = img_rgb.astype(np.float32)
    eps = 1e-6
    norm = (np.mean(np.power(I, p), axis=(0, 1)) + eps) ** (1.0 / p)
    scale = np.clip(np.mean(norm) / norm, gain_min, gain_max)
    I *= scale
    return np.clip(I, 0, 255).astype(np.uint8)

def _percentile_tone(img_rgb: np.ndarray, lo: float = 2.0, hi: float = 98.0) -> np.ndarray:
    ycrcb = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2YCrCb)
    Y = ycrcb[:, :, 0].astype(np.float32)
    a, b = np.percentile(Y, lo), np.percentile(Y, hi)
    if b - a < 1.0:
        return img_rgb
    Yn = np.clip((Y - a) * (255.0 / (b - a)), 0, 255).astype(np.uint8)
    ycrcb[:, :, 0] = Yn
    return cv2.cvtColor(ycrcb, cv2.COLOR_YCrCb2RGB)

# ------------ Noise & sharpness (adaptive; softer at high acutance) ------------
def _estimate_noise_sigma(img_rgb: np.ndarray) -> float:
    gray = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2GRAY).astype(np.float32) / 255.0
    hp = gray - cv2.GaussianBlur(gray, (0, 0), 1.5)
    return float(np.std(hp))

def _denoise_and_unsharp(img_rgb: np.ndarray) -> np.ndarray:
    sigma = _estimate_noise_sigma(img_rgb)
    h_chroma = float(np.interp(sigma, [0.005, 0.03], [3.0, 9.0]))
    ycrcb = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2YCrCb)
    Y, Cr, Cb = ycrcb[:, :, 0], ycrcb[:, :, 1], ycrcb[:, :, 2]
    Cr_d = cv2.fastNlMeansDenoising(Cr, None, h=h_chroma, templateWindowSize=7, searchWindowSize=21)
    Cb_d = cv2.fastNlMeansDenoising(Cb, None, h=h_chroma, templateWindowSize=7, searchWindowSize=21)
    acut = cv2.Laplacian(Y, cv2.CV_32F).var()
    base_amt = float(np.interp(acut, [50.0, 300.0], [0.10, 0.05]))
    amt = min(0.10, max(0.04, base_amt))
    Y_blur = cv2.GaussianBlur(Y, (0, 0), 0.9)
    Y_sharp = cv2.addWeighted(Y, 1.0 + amt, Y_blur, -amt, 0)
    ycrcb_d = cv2.merge([Y_sharp, Cr_d, Cb_d])
    out = cv2.cvtColor(ycrcb_d, cv2.COLOR_YCrCb2RGB)
    return np.clip(out, 0, 255).astype(np.uint8)

# ------------ Eye micro-sharpen (landmark-based; optional) ------------
def _eye_micro_sharpen(rgb: np.ndarray) -> np.ndarray:
    h, w = rgb.shape[:2]
    det = _get_detector((w, h), score_threshold=0.85)
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    try:
        _, faces = det.detect(bgr)
    except Exception:
        faces = None
    if faces is None or len(faces) == 0:
        return rgb
    row = faces[0].astype(np.float32)
    lx, ly, rx, ry = float(row[4]), float(row[5]), float(row[6]), float(row[7])
    fh = float(row[3])
    r = max(6, int(round(0.06 * fh)))
    mask = np.zeros((h, w), np.float32)
    cv2.circle(mask, (int(lx), int(ly)), r, 1.0, -1, lineType=cv2.LINE_AA)
    cv2.circle(mask, (int(rx), int(ry)), r, 1.0, -1, lineType=cv2.LINE_AA)
    mask = cv2.GaussianBlur(mask, (0, 0), r * 0.6)[..., None]
    sharp = cv2.addWeighted(rgb, 1.08, cv2.GaussianBlur(rgb, (0, 0), 1.2), -0.08, 0)
    out = (mask * sharp + (1.0 - mask) * rgb).astype(np.uint8)
    return out

# ------------ Trim uniform borders & content-box enforce (keeps exact 4:5) ------------
def _trim_uniform_edges_to_4x5(rgb: np.ndarray, max_frac: float = _MAX_UNIFORM_TRIM) -> np.ndarray:
    h, w = rgb.shape[:2]
    max_t = int(round(h * max_frac))
    max_l = int(round(w * max_frac))

    def edge_is_uniform(band: np.ndarray) -> bool:
        return float(band.std()) < 3.0

    top = bottom = left = right = 0
    changed = True
    while changed:
        changed = False
        if top < max_t and edge_is_uniform(rgb[top:top+4, :, :]): top += 2; changed = True
        if bottom < max_t and edge_is_uniform(rgb[h-bottom-4:h-bottom, :, :]): bottom += 2; changed = True
        if left < max_l and edge_is_uniform(rgb[:, left:left+4, :]): left += 2; changed = True
        if right < max_l and edge_is_uniform(rgb[:, w-right-4:w-right, :]): right += 2; changed = True

    rgb = rgb[top:h-bottom, left:w-right]
    h, w = rgb.shape[:2]

    # content-driven bbox from gradient magnitude (avoid corner triangles)
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    g = _grad_mag(gray)
    thr = max(5.0, 0.45 * float(g.mean()))
    content = (g > thr).astype(np.uint8) * 255
    k = max(3, int(round(min(h, w) * 0.01)))
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
    content = cv2.morphologyEx(content, cv2.MORPH_CLOSE, kernel, 2)
    ys, xs = np.where(content > 0)
    if ys.size > 0:
        y1, y2 = int(ys.min()), int(ys.max())
        x1, x2 = int(xs.min()), int(xs.max())
        # add small margin
        m = max(2, int(round(min(h, w) * 0.01)))
        y1 = max(0, y1 - m); y2 = min(h, y2 + m)
        x1 = max(0, x1 - m); x2 = min(w, x2 + m)
        rgb = rgb[y1:y2, x1:x2]
        h, w = rgb.shape[:2]

    # enforce exact 4:5 by central trim if needed
    target_w = int(round(h * 0.8))
    if w > target_w:
        excess = w - target_w
        l = excess // 2
        rgb = rgb[:, l:l+target_w]
    elif w < target_w:
        target_h = int(round(w / 0.8))
        excess = h - target_h
        t = max(0, excess // 2)
        rgb = rgb[t:t+target_h, :]
    return rgb

# ------------ 4:5 crop with consistent head size & 2D anti-selfie scoring ------------
def _portrait_crop_4x5(img_bgr: np.ndarray, box_xywh: Tuple[float, float, float, float], padding_px: int) -> Image.Image:
    H, W = img_bgr.shape[:2]
    x, y, w, h = map(float, box_xywh)
    aspect = 4.0 / 5.0

    target_h = max(h / max(_TARGET_FACE_FRAC, 1e-3), h + 2.0 * padding_px)
    target_w = max(target_h * aspect, w * 1.6)

    cx = x + w / 2.0
    cy = y + h * 0.55  # shoulders bias

    # low-res scoring maps
    small_w = max(1, W // 3); small_h = max(1, H // 3)
    small_rgb = cv2.cvtColor(cv2.resize(img_bgr, (small_w, small_h), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2RGB)
    skin = _skin_mask(small_rgb)
    grad_small = _grad_mag(cv2.cvtColor(small_rgb, cv2.COLOR_RGB2GRAY))
    sx = W / small_w; sy = H / small_h

    best = (cx, cy, target_w, target_h, -1.0)
    for dx in np.linspace(-0.14, 0.14, 7):
        for dy in np.linspace(-0.08, 0.08, 5):
            cx_try = cx + dx * target_w
            cy_try = cy + dy * target_h
            th, tw = target_h, target_w
            for _ in range(4):
                x1 = int(round(cx_try - tw / 2)); y1 = int(round(cy_try - th / 2))
                x2 = int(round(cx_try + tw / 2)); y2 = int(round(cy_try + th / 2))
                if x1 >= 0 and y1 >= 0 and x2 <= W and y2 <= H:
                    break
                th *= 0.94
                tw = max(th * aspect, w * 1.6)
                cx_try = float(np.clip(cx_try, tw / 2, W - tw / 2))
                cy_try = float(np.clip(cy_try, th / 2, H - th / 2))

            xs1, ys1 = int(max(0, x1 / sx)), int(max(0, y1 / sy))
            xs2, ys2 = int(min(small_w, x2 / sx)), int(min(small_h, y2 / sy))
            area = max(1, (xs2 - xs1) * (ys2 - ys1))
            skin_score = float(skin[ys1:ys2, xs1:xs2].sum()) / area
            tex_pen = _edge_low_texture_penalty(grad_small, xs1, ys1, xs2, ys2)
            score = float(skin_score - _EDGE_PENALTY_LAMBDA * tex_pen)
            if score > best[4]:
                best = (cx_try, cy_try, tw, th, score)

    cx, cy, target_w, target_h, _ = best

    # final clamp + tiny shrink away from frame
    for _ in range(2):
        cx = float(np.clip(cx, target_w / 2, W - target_w / 2))
        cy = float(np.clip(cy, target_h / 2, H - target_h / 2))
        x1 = int(round(cx - target_w / 2)); y1 = int(round(cy - target_h / 2))
        x2 = int(round(cx + target_w / 2)); y2 = int(round(cy + target_h / 2))
        if x1 <= 0 or y1 <= 0 or x2 >= W or y2 >= H:
            target_h *= 0.985; target_w *= 0.985
        else:
            break

    x1 = max(0, int(round(cx - target_w / 2))); y1 = max(0, int(round(cy - target_h / 2)))
    x2 = min(W, int(round(cx + target_w / 2))); y2 = min(H, int(round(cy + target_h / 2)))

    crop_bgr = img_bgr[y1:y2, x1:x2]
    rgb = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB)
    rgb = _trim_uniform_edges_to_4x5(rgb, max_frac=_MAX_UNIFORM_TRIM)
    return Image.fromarray(rgb)

def _crop_with_padding(img_bgr: np.ndarray, box_xywh: Tuple[float, float, float, float], padding_px: int = 50) -> Image.Image:
    return _portrait_crop_4x5(img_bgr, box_xywh, padding_px)

# ------------ Resize to canonical 4:5 ------------
def _resize_to_4x5_long_side(rgb: np.ndarray, long_side: int) -> np.ndarray:
    h, w = rgb.shape[:2]
    target_h = long_side
    target_w = int(round(target_h * 0.8))
    return cv2.resize(rgb, (target_w, target_h), interpolation=cv2.INTER_CUBIC)

# ------------ Public API (unchanged) ------------
def detect_and_crop_face(image_bytes: bytes, padding_px: int = 300) -> tuple[FaceDetectionResult, bytes | None]:
    """
    Finds exactly one face in the image and returns a PNG with the cropped face and padding.
    Output is a vertical 4:5 PNG with unified long side (_OUTPUT_LONG_SIDE).
    """
    img_bgr = _read_bgr_with_exif(image_bytes)
    if img_bgr is None or img_bgr.size == 0:
        return "NO_FACE", None
    H, W = img_bgr.shape[:2]

    # 1) Face detection (strict + relaxed)
    det = _get_detector((W, H), score_threshold=0.90)
    try:
        _, faces = det.detect(img_bgr)
    except Exception:
        faces = None
    if faces is None or len(faces) == 0:
        det_relaxed = _get_detector((W, H), score_threshold=0.80)
        try:
            _, faces = det_relaxed.detect(img_bgr)
        except Exception:
            faces = None
    if faces is None or len(faces) == 0:
        return "NO_FACE", None
    if len(faces) > 1:
        return "MULTIPLE_FACES", None

    row = faces[0].astype(np.float32)
    x, y, w, h = map(float, row[:4])

    # 2) In-plane alignment using neutral border fill (no reflect)
    try:
        angle_deg, (cx, cy) = _compute_eye_angle_and_center(row)
        border_sample = np.median(np.concatenate([
            img_bgr[:max(2, H//200), :, :].reshape(-1, 3),
            img_bgr[-max(2, H//200):, :, :].reshape(-1, 3),
            img_bgr[:, :max(2, W//200), :].reshape(-1, 3),
            img_bgr[:, -max(2, W//200):, :].reshape(-1, 3)
        ], axis=0), axis=0).astype(np.uint8).tolist()
        M = cv2.getRotationMatrix2D((cx, cy), angle_deg, 1.0)
        img_bgr = cv2.warpAffine(
            img_bgr, M, (W, H), flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT, borderValue=border_sample
        )
        x, y, w, h = _rotate_box(x, y, w, h, angle_deg, (cx, cy))
    except Exception:
        pass

    # 3) 4:5 crop (consistent head size, 2D anti-selfie centering, anti-border)
    cropped = _crop_with_padding(img_bgr, (x, y, w, h), padding_px=padding_px)

    # 4) Color/tone + adaptive chroma-denoise + luma-unsharp
    rgb = np.array(cropped)
    rgb = _shades_of_gray_wb(rgb, p=6.0, gain_min=0.92, gain_max=1.08)
    rgb = _percentile_tone(rgb, 2.0, 98.0)
    rgb = _denoise_and_unsharp(rgb)

    # 5) Gentle eye micro-sharpen (improves identity, doesn't plasticize skin)
    rgb = _eye_micro_sharpen(rgb)

    # 6) Standardize size (vertical 4:5)
    rgb = _resize_to_4x5_long_side(rgb, _OUTPUT_LONG_SIDE)

    out = Image.fromarray(rgb)
    with io.BytesIO() as buf:
        out.save(buf, format="PNG")
        return "SUCCESS", buf.getvalue()

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

# Neutral fallback background (BGR). Never use black or saturated colors.
TIKTOK_BG_FALLBACK_BGR = (128, 128, 128)

# --- Anti-grid / anti-border controls ---
FEATHER_PX = 16                 # feather width inside collage (not at outer edges)
FEATHER_NOISE_STRENGTH = 0.08   # irregular feather modulation [0..1]
ROTATION_DEG_MAX = 1.2          # tiny random rotation per tile
PERSPECTIVE_JITTER_PX = 2       # subpixel perspective jitter around tile corners

# Background: gradient + low-frequency noise + tiny white noise
BG_NOISE_STD = 2.0              # per-pixel gaussian noise
BG_LF_NOISE_AMP = 6.0           # low-frequency noise amplitude
BG_GRADIENT_AMP = 10            # linear gradient amplitude

# Underlay (content to edges so model never sees flat bars)
UNDERLAY_OPACITY = 0.75         # blend factor [0..1] over the base background
UNDERLAY_SAT_MUL = 0.45         # desaturation to keep neutral
UNDERLAY_GAUSS_SIGMA = 65.0     # heavy blur so no identity leakage

REQUIRED_TILES_PER_EDGE = 1     # at least N tiles must touch each edge

# ---------------- I/O ----------------

def load_image_bgr_from_bytes(data: bytes) -> Optional[np.ndarray]:
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
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    buf = io.BytesIO()
    Image.fromarray(img_rgb).save(buf, format="JPEG", quality=quality, optimize=True)
    return buf.getvalue()

# --------------- Face prep ---------------

def _extract_and_prepare_faces(
    image_bytes_list: List[bytes],
    target_face_width: int
) -> List[np.ndarray]:
    prepared_faces = []
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
            if not results.detections or len(results.detections) != 1:
                continue

            det = results.detections[0]
            box = det.location_data.relative_bounding_box
            face_x = int(box.xmin * img_w)
            face_y = int(box.ymin * img_h)
            face_w = int(box.width * img_w)
            face_h = int(box.height * img_h)

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

            scale = target_face_width / cw
            new_h = max(1, int(ch * scale))
            resized = cv2.resize(cropped, (target_face_width, new_h), interpolation=cv2.INTER_AREA)

            # micro warps to break perfect grid cues
            rotated = _apply_micro_rotation(resized, max_deg=ROTATION_DEG_MAX)
            warped = _apply_micro_perspective(rotated, jitter_px=PERSPECTIVE_JITTER_PX)

            prepared_faces.append(warped)
    return prepared_faces

# --------------- Anti-grid helpers ---------------

def _apply_micro_rotation(img: np.ndarray, max_deg: float) -> np.ndarray:
    if max_deg <= 0:
        return img
    h, w = img.shape[:2]
    angle = np.random.uniform(-max_deg, max_deg)
    M = cv2.getRotationMatrix2D((w/2, h/2), angle, 1.0)
    return cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT101)

def _apply_micro_perspective(img: np.ndarray, jitter_px: int) -> np.ndarray:
    if jitter_px <= 0:
        return img
    h, w = img.shape[:2]
    j = float(jitter_px)
    src = np.float32([[0,0],[w,0],[w,h],[0,h]])
    dst = np.float32([
        [np.random.uniform(-j, j), np.random.uniform(-j, j)],
        [w + np.random.uniform(-j, j), np.random.uniform(-j, j)],
        [w + np.random.uniform(-j, j), h + np.random.uniform(-j, j)],
        [np.random.uniform(-j, j), h + np.random.uniform(-j, j)],
    ])
    M = cv2.getPerspectiveTransform(src, dst)
    return cv2.warpPerspective(img, M, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT101)

def _make_base_bg(canvas_h: int, canvas_w: int, base_bgr: Tuple[int,int,int]) -> np.ndarray:
    """Neutral background with linear gradient + low-frequency noise + tiny white noise."""
    canvas = np.full((canvas_h, canvas_w, 3), base_bgr, dtype=np.float32)

    if BG_GRADIENT_AMP > 0:
        theta = np.random.uniform(0, 2*np.pi)
        vx, vy = np.cos(theta), np.sin(theta)
        X, Y = np.meshgrid(np.linspace(-1,1,canvas_w), np.linspace(-1,1,canvas_h))
        grad = (X*vx + Y*vy) * BG_GRADIENT_AMP
        for c in range(3):
            canvas[:,:,c] = np.clip(canvas[:,:,c] + grad, 0, 255)

    if BG_LF_NOISE_AMP > 0:
        small_h = max(8, canvas_h // 32)
        small_w = max(8, canvas_w // 32)
        low = np.random.randn(small_h, small_w).astype(np.float32)
        low = cv2.GaussianBlur(low, (0,0), sigmaX=1.2, sigmaY=1.2)
        low = cv2.resize(low, (canvas_w, canvas_h), interpolation=cv2.INTER_CUBIC)
        low = cv2.GaussianBlur(low, (0,0), sigmaX=3.0, sigmaY=3.0)
        for c in range(3):
            canvas[:,:,c] = np.clip(canvas[:,:,c] + low * BG_LF_NOISE_AMP, 0, 255)

    if BG_NOISE_STD > 0:
        canvas += np.random.normal(0.0, BG_NOISE_STD, canvas.shape).astype(np.float32)

    return np.clip(canvas, 0, 255).astype(np.uint8)

def _make_underlay_from_tile(tile: np.ndarray, canvas_w: int, canvas_h: int) -> np.ndarray:
    """Create blurred, desaturated content underlay that fills the canvas edge-to-edge."""
    th, tw = tile.shape[:2]
    scale = max(canvas_w / tw, canvas_h / th)
    new_w, new_h = int(tw * scale), int(th * scale)
    resized = cv2.resize(tile, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

    # center-crop to canvas
    x0 = (new_w - canvas_w) // 2
    y0 = (new_h - canvas_h) // 2
    cropped = resized[y0:y0+canvas_h, x0:x0+canvas_w]

    # heavy blur + desaturate
    ksize = int(max(3, round(UNDERLAY_GAUSS_SIGMA * 3)) * 2 + 1)
    blurred = cv2.GaussianBlur(cropped, (ksize, ksize), UNDERLAY_GAUSS_SIGMA)
    hsv = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV).astype(np.float32)
    hsv[:,:,1] *= UNDERLAY_SAT_MUL
    hsv[:,:,1] = np.clip(hsv[:,:,1], 0, 255)
    desat = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)
    return desat

# --------------- Packing ---------------

def _attempt_greedy_pack(
    scaled_faces: List[np.ndarray], canvas_w: int, canvas_h: int
) -> Optional[List[Dict]]:
    sorted_faces = sorted(scaled_faces, key=lambda f: f.shape[0] * f.shape[1], reverse=True)
    placed_items = []
    canvas_center = np.array([canvas_w / 2, canvas_h / 2])

    def check_overlap(new_rect, placed_rects):
        x1, y1, w1, h1 = new_rect
        for item in placed_rects:
            x2, y2, w2, h2 = item['rect']
            if not (x1 + w1 <= x2 or x1 >= x2 + w2 or y1 + h1 <= y2 or y1 >= y2 + h2):
                return True
        return False

    if not sorted_faces:
        return []

    first = sorted_faces[0]
    fh, fw = first.shape[:2]
    x, y = (canvas_w - fw) // 2, (canvas_h - fh) // 2
    if x < 0 or y < 0 or x + fw > canvas_w or y + fh > canvas_h:
        return None
    placed_items.append({'rect': (x, y, fw, fh), 'img': first})

    for face in sorted_faces[1:]:
        fh, fw = face.shape[:2]
        best_pos, min_cost = None, float('inf')
        for item in placed_items:
            pr_x, pr_y, pr_w, pr_h = item['rect']
            candidates = [
                (pr_x + pr_w, pr_y), (pr_x - fw, pr_y),
                (pr_x, pr_y + pr_h), (pr_x, pr_y - fh),
                (pr_x + pr_w, pr_y + pr_h - fh), (pr_x - fw, pr_y - fh),
                (pr_x - fw, pr_y + pr_h), (pr_x + pr_w - fw, pr_y - fh),
            ]
            for cand_x, cand_y in candidates:
                if (0 <= cand_x and cand_x + fw <= canvas_w and
                    0 <= cand_y and cand_y + fh <= canvas_h and
                    not check_overlap((cand_x, cand_y, fw, fh), placed_items)):
                    center = np.array([cand_x + fw / 2, cand_y + fh / 2])
                    dist_sq = float(np.sum((center - canvas_center) ** 2))
                    margin_left = cand_x
                    margin_right = canvas_w - (cand_x + fw)
                    margin_top = cand_y
                    margin_bottom = canvas_h - (cand_y + fh)
                    edge_reward = 0.25 * min(margin_left, margin_right, margin_top, margin_bottom)
                    cost = dist_sq - (edge_reward ** 2)
                    if cost < min_cost:
                        min_cost = cost
                        best_pos = (cand_x, cand_y)

        if best_pos:
            placed_items.append({'rect': (best_pos[0], best_pos[1], fw, fh), 'img': face})
        else:
            return None

    return placed_items


def _snap_layout_to_edges(layout: List[Dict], canvas_w: int, canvas_h: int) -> None:
    if not layout:
        return
    min_y = min(item['rect'][1] for item in layout)
    for item in layout:
        x, y, w, h = item['rect']
        if y == min_y:
            item['rect'] = (x, 0, w, h)
    max_bottom = max(item['rect'][1] + item['rect'][3] for item in layout)
    for item in layout:
        x, y, w, h = item['rect']
        if y + h == max_bottom:
            item['rect'] = (x, canvas_h - h, w, h)
    min_x = min(item['rect'][0] for item in layout)
    for item in layout:
        x, y, w, h = item['rect']
        if x == min_x:
            item['rect'] = (0, y, w, h)
    max_right = max(item['rect'][0] + item['rect'][2] for item in layout)
    for item in layout:
        x, y, w, h = item['rect']
        if x + w == max_right:
            item['rect'] = (canvas_w - w, y, w, h)

def _ensure_edges_have_tiles(layout: List[Dict], canvas_w: int, canvas_h: int) -> None:
    if not layout:
        return

    def count_touching(edge):
        c = 0
        for item in layout:
            x, y, w, h = item['rect']
            if edge == 'L' and x == 0: c += 1
            if edge == 'R' and x + w == canvas_w: c += 1
            if edge == 'T' and y == 0: c += 1
            if edge == 'B' and y + h == canvas_h: c += 1
        return c

    for edge in ['L','R','T','B']:
        while count_touching(edge) < REQUIRED_TILES_PER_EDGE:
            best, best_gap = None, 1e9
            for item in layout:
                x, y, w, h = item['rect']
                if edge == 'L':
                    gap = x; new_rect = (0, y, w, h)
                elif edge == 'R':
                    gap = canvas_w - (x + w); new_rect = (canvas_w - w, y, w, h)
                elif edge == 'T':
                    gap = y; new_rect = (x, 0, w, h)
                else:
                    gap = canvas_h - (y + h); new_rect = (x, canvas_h - h, w, h)
                if gap < best_gap:
                    best_gap, best = gap, (item, new_rect)
            if best is None:
                break
            best[0]['rect'] = best[1]

# --------------- Paste tiles ---------------

def _irregular_alpha(h: int, w: int, feather_px: int) -> np.ndarray:
    alpha = np.ones((h, w), dtype=np.float32)
    if feather_px <= 0:
        return alpha
    fy = min(feather_px, h // 2)
    fx = min(feather_px, w // 2)
    ramp_x = np.linspace(0, 1, fx, dtype=np.float32)
    ramp_y = np.linspace(0, 1, fy, dtype=np.float32)
    alpha[:, :fx] *= ramp_x
    alpha[:, -fx:] *= ramp_x[::-1]
    alpha[:fy, :] *= ramp_y[:, None]
    alpha[-fy:, :] *= ramp_y[::-1][:, None]

    if FEATHER_NOISE_STRENGTH > 0:
        small = np.random.rand(max(8, h//16), max(8, w//16)).astype(np.float32)
        noise = cv2.resize(cv2.GaussianBlur(small, (0,0), 1.0), (w, h), interpolation=cv2.INTER_CUBIC)
        noise = cv2.GaussianBlur(noise, (0,0), 2.0)
        noise = 1.0 - FEATHER_NOISE_STRENGTH + FEATHER_NOISE_STRENGTH * noise
        alpha *= noise

    return np.clip(alpha, 0.0, 1.0)

def _harden_edges_touching_canvas(alpha: np.ndarray,
                                  touch_left: bool, touch_right: bool,
                                  touch_top: bool, touch_bottom: bool,
                                  feather_px: int) -> np.ndarray:
    """Disable feathering where tile touches canvas edge: true full-bleed."""
    h, w = alpha.shape
    px = min(feather_px, max(1, min(h, w)//4))
    if touch_left:
        alpha[:, :px] = 1.0
    if touch_right:
        alpha[:, w-px:] = 1.0
    if touch_top:
        alpha[:px, :] = 1.0
    if touch_bottom:
        alpha[h-px:, :] = 1.0
    return alpha

# --------------- Core pack ---------------

def _pack_faces_with_scaling(
    faces: List[np.ndarray],
    canvas_w: int,
    canvas_h: int,
    bg_color_bgr: Tuple[int, int, int]
) -> np.ndarray:
    """
    Binary search the scale + greedy pack; paste with irregular feathered edges.
    Background = base (gradient+noise) + blurred, desaturated content underlay.
    """
    base_bg = _make_base_bg(canvas_h, canvas_w, bg_color_bgr)
    if not faces:
        return base_bg

    low_scale = 0.1
    total_face_area = sum(f.shape[0] * f.shape[1] for f in faces)
    canvas_area = canvas_w * canvas_h
    high_scale = (math.sqrt(canvas_area / total_face_area) * 1.5) if total_face_area > 0 else low_scale

    best_layout = None
    scaled_at_best = None
    for _ in range(10):
        if high_scale - low_scale < 0.01:
            break
        mid_scale = (low_scale + high_scale) / 2.0
        scaled_faces = []
        try:
            for f in faces:
                h, w = f.shape[:2]
                new_w, new_h = int(w * mid_scale), int(h * mid_scale)
                if new_w > 0 and new_h > 0:
                    scaled_faces.append(cv2.resize(f, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4))
        except cv2.error:
            scaled_faces = []

        if not scaled_faces:
            high_scale = mid_scale
            continue

        layout = _attempt_greedy_pack(scaled_faces, canvas_w, canvas_h)
        if layout is not None:
            best_layout = layout
            scaled_at_best = scaled_faces
            low_scale = mid_scale
        else:
            high_scale = mid_scale

    if not best_layout:
        return base_bg

    _snap_layout_to_edges(best_layout, canvas_w, canvas_h)
    _ensure_edges_have_tiles(best_layout, canvas_w, canvas_h)

    # --- Content underlay from largest tile to kill "flat bars" priors ---
    largest_tile = max(scaled_at_best, key=lambda im: im.shape[0]*im.shape[1])
    underlay = _make_underlay_from_tile(largest_tile, canvas_w, canvas_h)
    canvas = cv2.addWeighted(underlay, UNDERLAY_OPACITY, base_bg, 1.0 - UNDERLAY_OPACITY, 0.0)

    # Prepare mask of remaining background (for final tiny noise)
    bg_mask = np.ones((canvas_h, canvas_w), dtype=np.uint8) * 255

    for item in best_layout:
        x, y, w, h = item['rect']
        tile = item['img']

        alpha = _irregular_alpha(h, w, FEATHER_PX)
        touch_left = (x == 0)
        touch_right = (x + w == canvas_w)
        touch_top = (y == 0)
        touch_bottom = (y + h == canvas_h)
        alpha = _harden_edges_touching_canvas(alpha, touch_left, touch_right, touch_top, touch_bottom, FEATHER_PX)

        roi = canvas[y:y+h, x:x+w].astype(np.float32)
        tile_f = tile.astype(np.float32)
        alpha_3 = np.dstack([alpha, alpha, alpha])
        out = tile_f * alpha_3 + roi * (1.0 - alpha_3)
        canvas[y:y+h, x:x+w] = np.clip(out, 0, 255).astype(np.uint8)

        bg_mask[y:y+h, x:x+w][(alpha * 255).astype(np.uint8) > 0] = 0

    if BG_NOISE_STD > 0:
        noise = np.random.normal(0.0, BG_NOISE_STD, (canvas_h, canvas_w, 3)).astype(np.float32)
        noise *= (bg_mask[:, :, None] > 0).astype(np.float32)
        canvas = np.clip(canvas.astype(np.float32) + noise, 0, 255).astype(np.uint8)

    return canvas

# --------------- Public API ---------------

def create_portrait_collage_from_bytes(image_bytes_list: List[bytes]) -> Optional[bytes]:
    """
    Build a dense portrait collage that visually suggests full-bleed composition.
    Keeps the canvas size strictly 1440x1280.
    """
    if not image_bytes_list:
        return None
    try:
        faces = _extract_and_prepare_faces(image_bytes_list, target_face_width=300)
        if not faces:
            logger.warning("No faces could be prepared from the provided images.")
            return None
        final_canvas = _pack_faces_with_scaling(faces, TIKTOK_CANVAS_W, TIKTOK_CANVAS_H, TIKTOK_BG_FALLBACK_BGR)
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

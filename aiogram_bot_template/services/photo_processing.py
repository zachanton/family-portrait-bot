# aiogram_bot_template/services/photo_processing.py
import cv2
import io
import uuid
import mediapipe as mp
import numpy as np
import structlog
from typing import Optional, Tuple, Dict
from PIL import Image, ImageOps

logger = structlog.get_logger(__name__)

# --- MediaPipe setup ---
mp_face_mesh = mp.solutions.face_mesh
mp_selfie_segmentation = mp.solutions.selfie_segmentation

# FaceMesh landmark indices
FOREHEAD_TOP, CHIN_BOTTOM = 10, 152
LEFT_EYE_OUTER, RIGHT_EYE_OUTER = 263, 33
LEFT_FACE_OUTER, RIGHT_FACE_OUTER = 234, 454  # cheek extremes

# --- Pipeline parameters ---
# Face scale normalization: geometric mean of IOD and forehead→chin height
TARGET_FACE_METRIC_PX = 220.0
MIN_SCALE, MAX_SCALE = 0.60, 1.80

SEGMENTATION_THRESHOLD = 0.10

# Initial guess for background overlap; final seam is adapted by head bounds
OVERLAP_RATIO = 0.30

# Heads must be close but NEVER touch; minimal horizontal head gap
HEAD_MARGIN_RATIO_OF_HEADH = 0.12   # % of average head height
HEAD_MARGIN_PX_MIN = 18             # absolute floor in px

# Head horizontal bounds are measured inside a vertical strip around the head
# relative to forehead→chin span on the rotated image
HEAD_STRIP_TOP_EXTRA = 0.25   # include a bit above forehead
HEAD_STRIP_BOTTOM_EXTRA = 0.10  # include a bit below chin

# Seam softening on BACKGROUND only (people are pasted afterwards)
SEAM_SOFTEN_PX = 26
SEAM_SOFTEN_SIGMA = 6.0

EDGE_BLUR_KSIZE = 99
CROP_ASPECT = 0.75

DEBUG_OVERLAYS = True


# --- I/O ---

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


def paste_transparent(background: np.ndarray, foreground: np.ndarray, x: int, y: int) -> np.ndarray:
    """Alpha-composite RGBA foreground over BGR background at (x, y)."""
    h, w = foreground.shape[:2]
    y_end, x_end = min(y + h, background.shape[0]), min(x + w, background.shape[1])
    h, w = y_end - y, x_end - x
    if w <= 0 or h <= 0:
        return background
    fg = foreground[:h, :w]
    alpha = fg[:, :, 3].astype(np.float32) / 255.0
    alpha_3 = np.dstack((alpha, alpha, alpha))
    bg_slice = background[y:y_end, x:x_end].astype(np.float32)
    blend = bg_slice * (1.0 - alpha_3) + fg[:, :, :3].astype(np.float32) * alpha_3
    background[y:y_end, x:x_end] = np.clip(blend, 0, 255).astype(np.uint8)
    return background


# --- Analysis ---

def analyze_and_segment_person(img_bgr: np.ndarray) -> Dict:
    """Return image, face landmarks and person segmentation mask."""
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)

    with mp_face_mesh.FaceMesh(
        static_image_mode=True,
        max_num_faces=1,
        refine_landmarks=False,
        min_detection_confidence=0.5,
    ) as fm:
        res = fm.process(img_rgb)
        if not res.multi_face_landmarks:
            raise ValueError("Face not found.")
        face_lm = res.multi_face_landmarks[0]

    with mp_selfie_segmentation.SelfieSegmentation(model_selection=0) as seg:
        seg_mask = seg.process(img_rgb).segmentation_mask

    return {"image_bgr": img_bgr, "face_landmarks": face_lm, "segmentation_mask": seg_mask}


def _lm_to_px(face_lm, w: int, h: int) -> np.ndarray:
    return np.array([(p.x * w, p.y * h) for p in face_lm.landmark], dtype=np.float32)


def get_interocular_distance(person_data: Dict) -> Optional[float]:
    img = person_data["image_bgr"]; h, w = img.shape[:2]
    lm = _lm_to_px(person_data["face_landmarks"], w, h)
    return float(np.linalg.norm(lm[LEFT_EYE_OUTER] - lm[RIGHT_EYE_OUTER]))


def get_head_height(person_data: Dict) -> Optional[float]:
    img = person_data["image_bgr"]; h, w = img.shape[:2]
    lm = _lm_to_px(person_data["face_landmarks"], w, h)
    return float(np.linalg.norm(lm[FOREHEAD_TOP] - lm[CHIN_BOTTOM]))


def face_scale_metric(person_data: Dict) -> Optional[float]:
    iod = get_interocular_distance(person_data)
    hh = get_head_height(person_data)
    if not iod or not hh or iod <= 0 or hh <= 0:
        return None
    return float(np.sqrt(iod * hh))


# --- Debug overlay ---

def _save_face_debug_overlay(img_bgr: np.ndarray, person_data: Dict, title: str) -> str:
    try:
        h, w = img_bgr.shape[:2]
        px = _lm_to_px(person_data["face_landmarks"], w, h)
        img = img_bgr.copy()
        p_le, p_re = px[LEFT_EYE_OUTER], px[RIGHT_EYE_OUTER]
        p_top, p_chin = px[FOREHEAD_TOP], px[CHIN_BOTTOM]
        iod = np.linalg.norm(p_le - p_re)
        hh = np.linalg.norm(p_top - p_chin)
        metric = np.sqrt(max(iod, 1e-6) * max(hh, 1e-6))
        cv2.line(img, tuple(p_le.astype(int)), tuple(p_re.astype(int)), (0, 255, 0), 2)
        cv2.line(img, tuple(p_top.astype(int)), tuple(p_chin.astype(int)), (255, 0, 0), 2)
        y0 = 30
        cv2.putText(img, f"IOD: {iod:.1f}", (10, y0), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,255,0), 2)
        cv2.putText(img, f"HeadH: {hh:.1f}", (10, y0+28), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255,0,0), 2)
        cv2.putText(img, f"Metric: {metric:.1f}", (10, y0+56), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,200,255), 2)
        cv2.putText(img, title, (10, h-12), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (240,240,240), 2)
        path = f"/tmp/portrait_debug_{uuid.uuid4().hex[:8]}.jpg"
        cv2.imwrite(path, img)
        return path
    except Exception:
        logger.exception("Failed to save debug overlay.")
        return ""


# --- Rotate to eyes-horizontal and compute alpha-based clearances + rotated face points ---

def _rotate_build_rgba_and_stats(person_data: Dict) -> Dict:
    img_bgr = person_data["image_bgr"]
    mask = person_data["segmentation_mask"]
    h, w = img_bgr.shape[:2]

    # RGBA via segmentation
    condition = np.stack((mask,) * 3, axis=-1) > SEGMENTATION_THRESHOLD
    person_bgr = np.where(condition, img_bgr, 0)
    alpha_channel = (np.clip(mask, 0.0, 1.0) * 255).astype(np.uint8)
    person_rgba = cv2.merge([*cv2.split(person_bgr), alpha_channel])

    # Rotate so the eye line is horizontal
    lm_px = _lm_to_px(person_data["face_landmarks"], w, h)
    p_le, p_re = lm_px[LEFT_EYE_OUTER], lm_px[RIGHT_EYE_OUTER]
    angle_deg = float(np.degrees(np.arctan2(p_le[1] - p_re[1], p_le[0] - p_re[0])))
    center_eyes = (p_le + p_re) / 2.0
    head_height = float(np.linalg.norm(lm_px[FOREHEAD_TOP] - lm_px[CHIN_BOTTOM]))

    M = cv2.getRotationMatrix2D((float(center_eyes[0]), float(center_eyes[1])), angle_deg, 1.0)
    rot_bgr = cv2.warpAffine(img_bgr, M, (w, h), flags=cv2.INTER_LINEAR, borderValue=(0, 0, 0))
    rot_rgba = cv2.warpAffine(person_rgba, M, (w, h), flags=cv2.INTER_LINEAR, borderValue=(0, 0, 0, 0))
    eyes_rot = M @ np.array([center_eyes[0], center_eyes[1], 1.0], dtype=np.float32)

    # Rotate key face points
    def _rot(pt):
        return M @ np.array([pt[0], pt[1], 1.0], dtype=np.float32)
    rot_pts = {
        "forehead": _rot(lm_px[FOREHEAD_TOP]),
        "chin": _rot(lm_px[CHIN_BOTTOM]),
        "cheek_L": _rot(lm_px[LEFT_FACE_OUTER]),
        "cheek_R": _rot(lm_px[RIGHT_FACE_OUTER]),
    }

    # Alpha bounds (whole person bbox)
    a = rot_rgba[:, :, 3]
    ys, xs = np.where(a > 10)
    if len(ys) == 0:
        top_y = 0; bot_y = h - 1; left_x = 0; right_x = w - 1
    else:
        top_y, bot_y = int(ys.min()), int(ys.max())
        left_x, right_x = int(xs.min()), int(xs.max())

    # Clearances from eyes
    up_clear = float(eyes_rot[1] - top_y)
    down_clear = float(bot_y - eyes_rot[1])

    return {
        "rot_bgr": rot_bgr,
        "rot_rgba": rot_rgba,
        "eyes_xy": (float(eyes_rot[0]), float(eyes_rot[1])),
        "head_h": head_height,
        "angle_deg": angle_deg,
        "bounds": {"top_y": top_y, "bot_y": bot_y, "left_x": left_x, "right_x": right_x},
        "clearances": {"up": up_clear, "down": down_clear},
        "rot_face_pts": rot_pts,
    }


# --- Helpers ---

def _resize(img: np.ndarray, scale: float) -> np.ndarray:
    if abs(scale - 1.0) < 1e-3:
        return img
    interp = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_CUBIC
    h, w = img.shape[:2]
    return cv2.resize(img, (int(round(w * scale)), int(round(h * scale))), interpolation=interp)


def _pad_crop_with_offsets(img: np.ndarray, x1: int, y1: int, x2: int, y2: int) -> Tuple[np.ndarray, int, int]:
    """Crop with replicate padding so we never change scale. Returns (crop, pad_left, pad_top)."""
    h, w = img.shape[:2]
    pad_left = max(0, -x1)
    pad_top = max(0, -y1)
    pad_right = max(0, x2 - w)
    pad_bottom = max(0, y2 - h)
    if any(v > 0 for v in (pad_left, pad_top, pad_right, pad_bottom)):
        img = cv2.copyMakeBorder(img, pad_top, pad_bottom, pad_left, pad_right, cv2.BORDER_REPLICATE)
        x1 += pad_left; x2 += pad_left; y1 += pad_top; y2 += pad_top
    return img[y1:y2, x1:x2], pad_left, pad_top


def _soften_vertical_band(img_bgr: np.ndarray, cx: int, width: int, sigma: float) -> None:
    """In-place: softly blur a vertical band centered at x=cx on BACKGROUND array."""
    if width <= 0:
        return
    h, w = img_bgr.shape[:2]
    x0 = max(0, int(cx - width // 2))
    x1 = min(w, int(cx + (width + 1) // 2))
    if x1 <= x0:
        return
    roi = img_bgr[:, x0:x1]
    blurred = cv2.GaussianBlur(roi, ksize=(0, 0), sigmaX=sigma, sigmaY=0)
    img_bgr[:, x0:x1] = blurred


def _head_bounds_x_in_crop(
    rot_rgba: np.ndarray,
    rot_pts: Dict,
    crop_origin_x: int,
    crop_origin_y: int,
    pad_left: int,
    pad_top: int,
    crop_w: int,
    crop_h: int,
    head_h: float
) -> Tuple[int, int]:
    """
    Compute horizontal head bounds (xmin, xmax) inside the crop.
    We take alpha within a vertical strip around the head from
    (forehead - HEAD_STRIP_TOP_EXTRA*head_h) to (chin + HEAD_STRIP_BOTTOM_EXTRA*head_h).
    This ignores shoulders/torso and focuses on the head.
    """
    fh = float(rot_pts["forehead"][1])
    ch = float(rot_pts["chin"][1])
    y_min = int(round(min(fh, ch) - HEAD_STRIP_TOP_EXTRA * head_h))
    y_max = int(round(max(fh, ch) + HEAD_STRIP_BOTTOM_EXTRA * head_h))
    H, W = rot_rgba.shape[:2]
    y_min = max(0, y_min); y_max = min(H - 1, y_max)
    if y_max <= y_min:
        y_min = max(0, int(min(fh, ch))); y_max = min(H - 1, int(max(fh, ch)))

    # Convert crop origins with padding into rotated coordinates
    x1 = crop_origin_x - pad_left
    y1 = crop_origin_y - pad_top
    x2 = x1 + crop_w
    y2 = y1 + crop_h

    # Intersect the head strip with the crop rect in rotated coords
    ys = slice(max(y_min, y1), min(y_max + 1, y2))
    xs = slice(max(x1, 0), min(x2, W))
    head_region = rot_rgba[ys, xs]
    a = head_region[:, :, 3]
    cols = np.where(a > 10)[1]
    if cols.size == 0:
        # Fallback: approximate by cheeks projected into crop coords
        cheek_L_x = int(round(float(rot_pts["cheek_L"][0]) - x1))
        cheek_R_x = int(round(float(rot_pts["cheek_R"][0]) - x1))
        xmin = max(0, min(cheek_L_x, cheek_R_x))
        xmax = min(crop_w - 1, max(cheek_L_x, cheek_R_x))
    else:
        xmin = int(cols.min())
        xmax = int(cols.max())

    return int(np.clip(xmin, 0, crop_w - 1)), int(np.clip(xmax, 0, crop_w - 1))


# --- Main ---

def create_composite_image(
    p1_bytes: bytes,
    p2_bytes: bytes
) -> Tuple[Optional[bytes], Optional[bytes], Optional[bytes]]:
    """
    Build composite with controlled head gap and also return pre-merge aligned portraits WITH background.

    Args:
        p1_bytes: right photo bytes (woman; will be placed in front)
        p2_bytes: left photo bytes (man)

    Returns:
        composite_jpeg: final composite as JPEG bytes (no alpha)
        left_aligned_jpeg: left aligned portrait (BGR) as JPEG bytes WITH background
        right_aligned_jpeg: right aligned portrait (BGR) as JPEG bytes WITH background
        On failure returns (None, None, None).
    """
    p1_bgr = load_image_bgr_from_bytes(p1_bytes)  # right (woman)
    p2_bgr = load_image_bgr_from_bytes(p2_bytes)  # left (man)
    if p1_bgr is None or p2_bgr is None:
        return None, None, None

    try:
        # --- Initial analysis
        d2 = analyze_and_segment_person(p2_bgr)
        d1 = analyze_and_segment_person(p1_bgr)

        s2 = face_scale_metric(d2); s1 = face_scale_metric(d1)
        iod2, hh2 = get_interocular_distance(d2), get_head_height(d2)
        iod1, hh1 = get_interocular_distance(d1), get_head_height(d1)
        logger.info("face_metrics_original",
            left={"w": p2_bgr.shape[1], "h": p2_bgr.shape[0], "IOD": iod2, "HeadH": hh2, "Metric": s2},
            right={"w": p1_bgr.shape[1], "h": p1_bgr.shape[0], "IOD": iod1, "HeadH": hh1, "Metric": s1},
            target_metric=TARGET_FACE_METRIC_PX
        )

        # --- Normalize head scales on full images
        def clamp(v, lo, hi): return max(lo, min(hi, v))
        scale2 = clamp(TARGET_FACE_METRIC_PX / s2, MIN_SCALE, MAX_SCALE)
        scale1 = clamp(TARGET_FACE_METRIC_PX / s1, MIN_SCALE, MAX_SCALE)
        p2s = _resize(p2_bgr, scale2)
        p1s = _resize(p1_bgr, scale1)
        d2s = analyze_and_segment_person(p2s)
        d1s = analyze_and_segment_person(p1s)

        if DEBUG_OVERLAYS:
            pathL = _save_face_debug_overlay(p2s, d2s, "LEFT scaled")
            pathR = _save_face_debug_overlay(p1s, d1s, "RIGHT scaled")
            logger.info("debug_overlays_scaled", left_path=pathL, right_path=pathR)

        iod2_s, iod1_s = get_interocular_distance(d2s), get_interocular_distance(d1s)
        hh2_s, hh1_s = get_head_height(d2s), get_head_height(d1s)
        logger.info("metrics_after_scaling",
            left={"IOD": iod2_s, "HeadH": hh2_s, "scale": scale2},
            right={"IOD": iod1_s, "HeadH": hh1_s, "scale": scale1}
        )

        # --- Rotate and collect stats + face points
        L = _rotate_build_rgba_and_stats(d2s)
        R = _rotate_build_rgba_and_stats(d1s)

        # Common vertical crop from eyes (consistent framing)
        up_L, down_L = L["clearances"]["up"], L["clearances"]["down"]
        up_R, down_R = R["clearances"]["up"], R["clearances"]["down"]
        head_h_avg = float((L["head_h"] + R["head_h"]) / 2.0)

        up_common = float(min(up_L, up_R))
        down_common = float(min(down_L, down_R))
        up_common = float(np.clip(up_common, 0.6 * head_h_avg, 1.3 * head_h_avg))
        down_common = float(np.clip(down_common, 0.8 * head_h_avg, 3.0 * head_h_avg))

        crop_h = int(round(up_common + down_common))
        crop_w = int(round(crop_h * CROP_ASPECT))

        logger.info("common_crop_vertical",
            up_L=up_L, down_L=down_L, up_R=up_R, down_R=down_R,
            head_h_avg=head_h_avg, chosen_up=up_common, chosen_down=down_common,
            crop_h=crop_h, crop_w=crop_w
        )

        # Crop both with replicate padding; keep offsets for head bounds conversion
        def crop_from_eyes_with_offsets(rot_img: np.ndarray, eyes_xy: Tuple[float, float]) -> Tuple[np.ndarray, int, int, int, int]:
            ex, ey = eyes_xy
            x1 = int(round(ex - crop_w / 2))
            y1 = int(round(ey - up_common))
            x2 = x1 + crop_w
            y2 = y1 + crop_h
            crop, pad_left, pad_top = _pad_crop_with_offsets(rot_img, x1, y1, x2, y2)
            return crop, x1, y1, pad_left, pad_top

        # Background crops (WITH background) — эти же кадры вернём пользователю
        left_bg, lx1, ly1, lpadx, lpady = crop_from_eyes_with_offsets(L["rot_bgr"], L["eyes_xy"])
        right_bg, rx1, ry1, rpadx, rpady = crop_from_eyes_with_offsets(R["rot_bgr"], R["eyes_xy"])

        # Person crops (RGBA) для наложения поверх фона в композите
        left_person_rgba, _, _, _, _ = crop_from_eyes_with_offsets(L["rot_rgba"], L["eyes_xy"])
        right_person_rgba, _, _, _, _ = crop_from_eyes_with_offsets(R["rot_rgba"], R["eyes_xy"])

        logger.info("cropped_sizes",
            left=(left_bg.shape[1], left_bg.shape[0]),
            right=(right_bg.shape[1], right_bg.shape[0]),
            equal_height=(left_bg.shape[0] == right_bg.shape[0])
        )

        # --- HEAD bounds inside the crops (ignore torso/shoulders)
        lhx0, lhx1 = _head_bounds_x_in_crop(
            L["rot_rgba"], L["rot_face_pts"], lx1, ly1, lpadx, lpady,
            left_bg.shape[1], left_bg.shape[0], L["head_h"]
        )
        rhx0, rhx1 = _head_bounds_x_in_crop(
            R["rot_rgba"], R["rot_face_pts"], rx1, ry1, rpadx, rpady,
            right_bg.shape[1], right_bg.shape[0], R["head_h"]
        )

        head_margin_px = int(max(HEAD_MARGIN_PX_MIN, HEAD_MARGIN_RATIO_OF_HEADH * head_h_avg))
        logger.info("head_strip_bounds_x",
            left_head_x=(lhx0, lhx1), right_head_x=(rhx0, rhx1), head_margin_px=head_margin_px
        )

        # --- Adaptive seam by HEAD boxes: enforce a margin between heads
        w_left, w_right = left_bg.shape[1], right_bg.shape[1]
        base_overlap = int(min(w_left, w_right) * OVERLAP_RATIO)

        start_right_base = w_left - base_overlap
        current_head_gap = (start_right_base + rhx0) - lhx1

        adjust = head_margin_px - current_head_gap
        overlap_px = base_overlap - int(round(adjust))
        overlap_px = int(np.clip(overlap_px, -min(64, max(w_left, w_right)), min(w_left, w_right)))
        right_x = w_left - overlap_px

        logger.info(
            "seam_from_heads",
            base_overlap_px=base_overlap,
            current_head_gap_px=current_head_gap,
            desired_head_margin_px=head_margin_px,
            overlap_px_final=overlap_px,
            right_start_x=right_x
        )

        # --- Compose BACKGROUND
        h = left_bg.shape[0]
        final_w = w_left + w_right - overlap_px
        composite_bg = np.zeros((h, final_w, 3), dtype=np.uint8)
        composite_bg[:, :w_left] = left_bg

        if overlap_px > 0:
            left_zone = composite_bg[:, right_x:right_x + overlap_px].astype(np.float32)
            right_zone = right_bg[:, :overlap_px].astype(np.float32)
            alpha = np.linspace(0, 1, overlap_px, dtype=np.float32)
            mask_3 = np.dstack([alpha] * 3)
            blended = left_zone * (1.0 - mask_3) + right_zone * mask_3
            composite_bg[:, right_x:right_x + overlap_px] = np.clip(blended, 0, 255).astype(np.uint8)
            composite_bg[:, right_x + overlap_px: right_x + w_right] = right_bg[:, overlap_px:]
        else:
            composite_bg[:, right_x: right_x + w_right] = right_bg

        # Soften seam on BACKGROUND only
        _soften_vertical_band(composite_bg, right_x, SEAM_SOFTEN_PX, SEAM_SOFTEN_SIGMA)
        logger.info("seam_soften", seam_x=right_x, width_px=SEAM_SOFTEN_PX, sigma=SEAM_SOFTEN_SIGMA)

        # --- Paste PEOPLE: woman (right) MUST be in front; bodies may overlap
        final_image = paste_transparent(composite_bg, left_person_rgba, 0, 0)
        final_image = paste_transparent(final_image, right_person_rgba, right_x, 0)

        # Optional soft edge treatment near outer canvas borders (avoid people zones)
        person_mask = np.zeros((h, final_w), dtype=np.uint8)
        if left_person_rgba.shape[2] == 4:
            ph, pw = left_person_rgba.shape[:2]
            person_mask[:ph, :pw] = np.maximum(person_mask[:ph, :pw], left_person_rgba[:, :, 3])
        if right_person_rgba.shape[2] == 4:
            ph, pw = right_person_rgba.shape[:2]
            person_mask[:ph, right_x:right_x + pw] = np.maximum(person_mask[:ph, right_x:right_x + pw], right_person_rgba[:, :, 3])

        kernel = np.ones((70, 70), np.uint8)
        safe_zone = cv2.dilate(person_mask, kernel, iterations=3)

        edge_mask = np.zeros((h, final_w), dtype=np.float32)
        cv2.rectangle(edge_mask, (0, 0), (final_w, h), 1.0, -1)
        margin = int(min(h, final_w) * 0.05)
        cv2.rectangle(edge_mask, (margin, margin), (final_w - margin, h - margin), 0.0, -1)
        edge_mask = cv2.GaussianBlur(edge_mask, (199, 199), 0)
        edge_mask[safe_zone > 0] = 0.0

        blurred = cv2.GaussianBlur(final_image, (EDGE_BLUR_KSIZE, EDGE_BLUR_KSIZE), 0)
        edge_mask_3 = cv2.cvtColor(edge_mask, cv2.COLOR_GRAY2BGR)
        final_image = (final_image.astype(np.float32) * (1.0 - edge_mask_3) +
                       blurred.astype(np.float32) * edge_mask_3)
        final_image = np.clip(final_image, 0, 255).astype(np.uint8)

        logger.info("final_composite",
                    final_size=(final_image.shape[1], final_image.shape[0]),
                    overlap_px=overlap_px,
                    right_start_x=right_x)

        # --- Encode outputs
        composite_jpeg = convert_bgr_to_jpeg_bytes(final_image)
        left_aligned_jpeg = convert_bgr_to_jpeg_bytes(left_bg)
        right_aligned_jpeg = convert_bgr_to_jpeg_bytes(right_bg)

        return composite_jpeg, left_aligned_jpeg, right_aligned_jpeg

    except Exception:
        logger.exception("A critical error occurred in create_composite_image.")
        return None, None, None


def crop_generated_image(image_bytes: bytes) -> Tuple[Optional[bytes], Optional[bytes]]:
    """Split the final composite in two halves."""
    try:
        img_np = load_image_bgr_from_bytes(image_bytes)
        if img_np is None:
            return None, None
        h, w, _ = img_np.shape
        midpoint = w // 2
        return convert_bgr_to_jpeg_bytes(img_np[:, :midpoint]), convert_bgr_to_jpeg_bytes(img_np[:, midpoint:])
    except Exception:
        logger.exception("Failed to crop generated image.")
        return None, None

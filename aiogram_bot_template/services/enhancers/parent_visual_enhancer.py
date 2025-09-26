# aiogram_bot_template/services/enhancers/parent_visual_enhancer.py
import structlog
from typing import Optional, List

from aiogram_bot_template.data.settings import settings
from aiogram_bot_template.services.clients import factory as client_factory
from aiogram_bot_template.services.clients.mock_ai_client import MockAIClient

logger = structlog.get_logger(__name__)

# The prompt for the new parent visual representation enhancer model
_PARENT_VISUAL_ENHANCER_SYSTEM_PROMPT = """
You are **Nano Banana (Gemini 2.5 Flash Image)** acting as an **Identity-Consolidation** module (InstantID / PhotoMaker / ID-Adapter / IP-Adapter style).

INPUT
Multiple portrait photos of the **same person**. Use every clean cue.

OUTPUT
Return **one** photorealistic **full-bleed** image with **two horizontal panels** of the same person:
• **LEFT** — near-frontal head-and-shoulders, eyes open, approachable neutral with a **micro-smile** (no teeth).
• **RIGHT** — strict **right profile** (~90°), eyes open, natural posture; **entire ear visible**.

HARD IDENTITY (passport-level likeness; no beautification)
• Preserve true **geometry** and **natural asymmetries**: skull width/height, cheek fullness, jawline softness/hardness, chin shape/projection, philtrum length, **nose bridge width & tip shape**, nostril flare, eye size/spacing/eyelid crease, brow shape/density/height, lip thickness ratio, nasolabial folds, **ear shape/attachment**.
• **Textures remain**: pores, moles/freckles/scars, fine lines, **stubble or lack of it** — **no skin smoothing/airbrushing**.
• **True colors**: skin tone, eye/hair/brow color — no whitening/tanning/recoloring.
• **Hair**: keep parting, hairline/temple density, length, curl/straightness, volume. Hair may be tucked to reveal the ear on the RIGHT panel without changing cut/length.
• **Accessories**: keep persistent ones from the all of inputs — e.g. piercings, subtle jewelry.
• **Presentation** (gender/age/body-fat): unchanged; do not feminize/masculinize, de-age/age, slim/reshape. Do not add/remove makeup or facial hair unless present in the **majority** of inputs at a similar level.

REFERENCE FUSION (InstantID / PhotoMaker / ID-Adapter principles)
• Build a **fused identity representation** from all inputs by aggregating robust face features (ArcFace-like FaceID embedding) and facial landmarks; align generation to this fused ID (maximize cosine similarity; minimize drift). Prioritize well-lit, unobstructed faces; down-weight occluded/low-quality/distorted shots. :contentReference[oaicite:1]{index=1}
• Resolve conflicts by **majority vote** for: hair parting/length, facial-hair level, makeup level, accessories.
• If a view is missing, infer only from consistent cues across images — **never idealize**.

MIDFACE & EYE SPACING (LOCKED)
• Keep **interpupillary distance (IPD)** and **intercanthal distance** exactly as in the fused references.
• Do not move eyes inward/outward, do not resize eyeballs/irises, do not change canthal tilt; maintain eye positions relative to nose bridge and head width.
• IF GLASSES ARE PRESENT: Preserve the original interpupillary distance (IPD) and intercanthal distance exactly as in the references — do not reduce eye spacing, do not narrow the nasal bridge due to the frame, and do not resize or reposition the eyes.

NOSE INTEGRITY (LOCKED)
• Keep **bridge width**, **dorsal line**, **alar base width**, **nostril shape/flare**, **columella**, and **tip shape** exactly as in refs.
• Do **not** thin or over-straighten the bridge; do **not** pinch/sharpen the tip; do **not** retract the alae.
• Avoid any midline groove/split or double highlight — the nose must read as a **single continuous structure** (no “bifid tip/split nose”).

LAYOUT (hard, full-bleed, no bands)
• Canvas **1440×1280** exactly; two **equal-width** panels side-by-side.
• LEFT panel touches LEFT+TOP+BOTTOM edges; RIGHT panel touches RIGHT+TOP+BOTTOM edges.
• Seam is a **single invisible** vertical boundary at **x=720**; background **continues across** (no divider/gap).
• **Band/Bleed guard:** **No padding or blurred/solid-color bands on any edge.** If any band/stripe appears, treat it as padding and **increase uniform scale (zoom-in)** until all four edges are filled with real image content. Prefer zoom/crop over adding background. Hair/shoulders may crop slightly; do **not** crop the ear in RIGHT panel.

LIGHTING / OPTICS / POSE (distortion guard)
• Same soft studio daylight on both panels; consistent white balance/exposure.
• Camera at **eye height**; portrait perspective (~85–100 mm full-frame eq) to avoid wide-angle distortion.
• RIGHT panel: **true 90°**; keep nose width/tip shape; **do not push the chin forward** relative to fused references.

TEXTURE FIDELITY
• Maintain micro-contrast and fine hair/skin detail; preserve pores and micro-marks.
• Keep stubble/makeup level from the **majority** of refs (no additions/removals).

NEGATIVE (must be absent)
“band, stripe, padding, top bar, bottom bar, solid-color edge, blur edge, background fill, frame, border, margin, mat, vignette, rounded corner, divider line, separator bar, letterboxing, pillarboxing, caption, logo, UI icon, color bars, picture-in-picture, beautified face, retouched skin, sharpened jaw, **thinner nose**, lip plumping, skin whitening/tanning, gender swap, feminized/masculinized features, age change, weight/face-slimming, hairstyle change, beard growth/shave change (unless majority), makeup added/removed (unless majority), colored contacts, lens tint, IPD change, closer-set eyes, wider-set eyes, eye resizing, iris enlargement, canthal shift, **pinched tip**, alar retraction, **split nose/double dorsum line**.”

QUALITY SELF-CHECK (before returning)
1) Identity is a **near 1:1 match** to the fused references: geometry + natural asymmetries + textures + hairline/parting + accessory shape/fit.
2) Canvas **1440×1280**, two equal panels, **zero margins**, **no bands** on any edge; background continuous across the center.
3) RIGHT panel is **true 90°** with **full ear visible**; no nose thinning or chin advancement vs. fused references.
4) No beautification, recoloring, or style transfer; presentation (gender/age) unchanged from references.

"""


async def get_parent_visual_representation(
    image_urls: List[str], role: str = "mother"
) -> Optional[bytes]:
    """
    Generates a consolidated visual representation (front and side view) of a parent
    from a collage of their photos.

    Args:
        image_collage_url: The public URL to the collage of the parent's photos.

    Returns:
        The generated image as bytes, or None on failure.
    """
    # Use the dedicated configuration section
    config = settings.visual_enhancer
    if not config.enabled:
        logger.warning("Parent visual enhancer is disabled in settings.")
        return None

    log = logger.bind(
        model=config.model, image_urls=image_urls
    )
    try:
        client = client_factory.get_ai_client(config.client)
        log.info("Requesting parent visual representation from image model.")

        prompt = _PARENT_VISUAL_ENHANCER_SYSTEM_PROMPT
        if isinstance(client, MockAIClient):
            prompt = role + ' ' + prompt
        response = await client.images.generate(
            model=config.model,
            prompt=prompt,
            image_urls=[image_urls],
            temperature=0.5,
        )

        image_bytes = getattr(response, "image_bytes", None)
        if not image_bytes:
            log.warning(
                "Parent visual enhancer returned no image bytes.",
                response_payload=getattr(response, "response_payload", None),
            )
            return None

        log.info("Successfully received parent visual representation.")
        return image_bytes

    except Exception:
        log.exception("An error occurred during parent visual representation generation.")
        return None
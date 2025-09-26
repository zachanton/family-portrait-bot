# aiogram_bot_template/services/enhancers/parent_visual_enhancer.py
import structlog
from typing import Optional, List

from aiogram_bot_template.data.settings import settings
from aiogram_bot_template.services.clients import factory as client_factory
from aiogram_bot_template.services.clients.mock_ai_client import MockAIClient

logger = structlog.get_logger(__name__)

# The prompt for the new parent visual representation enhancer model
_PARENT_VISUAL_ENHANCER_SYSTEM_PROMPT = """
You are **Nano Banana (Gemini 2.5 Flash Image)** acting as an **ID-consolidation** module (InstantID / PhotoMaker / ID-Adapter style).

**INPUT**: Multiple portrait photos of the **same person**.

**OUTPUT**: Return **one** photorealistic **full-bleed** image with **two horizontal panels** of the same person:
**LEFT** — near-frontal head-and-shoulders, eyes open, approachable neutral expression, **micro-smile**.
**RIGHT** — strict **right profile** (~90°), eyes open, natural posture.

**IDENTITY LOCK (very hard)**
- Maximize identity fidelity; treat identity cues as **lossless**. **Do not average toward a generic face.**
- Preserve subject-specific deviations from symmetry and canonical proportions.
- When references disagree, choose the variant that appears **in the majority of inputs** (or in the sharpest, most frontal input); never invent unseen features.
- Copy these micro-features **exactly** and keep them consistent across both panels:
  hairline geometry/height/part **and density**, eyebrow shape & thickness,
  eyelid shape and eye-size asymmetry, inter-ocular distance,
  nasal bridge contour and **nose-tip** shape/projection,
  philtrum length, lip shape and **corner angle**,
  beard/stubble density pattern (if present),
  chin projection, jaw angle, **ear rim/lobe notches**,
  **skin micro-texture**: pores, freckles, moles, tiny scars, mild redness.

**LANDMARK CONSTRAINTS (hard, quantitative)**
- Keep these within **±2–3%** of the scale defined by **inter-pupillary distance (IPD)**:
  inter-ocular distance; outer canthus positions; brow arch height; nose-tip projection and width at alar base;
  philtrum length; mouth width and lip-corner angle; chin apex position; jaw angle; ear height/helix outline.
- Preserve relative coordinates of distinctive freckles/moles (±2% of face width/height). Do not remove them.

**LAYOUT (hard, full-bleed)**
- Absolutely **no letterboxing or pillarboxing**.
- Use the reference image canvas exactly; **two equal-width panels** side-by-side.
- **Left panel touches LEFT+TOP+BOTTOM edges. Right panel touches RIGHT+TOP+BOTTOM edges.**
- Seam is a **single invisible vertical boundary at x=720** — **no drawn divider, no gap**; background **continues across the seam**.
- If any margin appears, **scale up** until the canvas is filled **edge-to-edge**.

**CONSISTENCY ACROSS PANELS (hard)**
- Same person in both panels.
- Hairline, freckles/moles/scars, stubble pattern, ear geometry and jawline must align logically between views.
- Match lighting, white balance and contrast across panels.

**WARDROBE / ACCESSORIES**
- Remove headwear.
- **Eyewear:** keep prescription glasses if they appear in the majority of inputs; do **not** add sunglasses; do **not** alter frame shape or lens reflections.

**LIGHTING / RENDERING**
- Neutral soft studio daylight; no “beauty” smoothing; keep natural skin texture and color variation.
- Use an 85–105 mm portrait perspective (no wide-angle distortion).

**NEGATIVE (must be absent)**
letterboxing, pillarboxing, caption, watermark, logo, UI icon, color bars, picture-in-picture,
beauty retouch, skin smoothing/airbrushing, makeup addition, symmetry correction, de-aging/aging,
face slimming, eye enlargement, nose reduction, tooth whitening, lip plumping, jawline sharpening,
hairline “fixing” or thickening, iris pattern enhancement, style transfer, cartoon/anime aesthetics.

**QUALITY CHECK before returning (fail ⇒ regenerate)**
1) Identity is a **1:1** match: all listed micro-features and **distinctive asymmetries** are present and consistent in both panels.
2) Quantitative tolerances met (±2–3% of IPD) for eyes, nose tip, lip corners, chin/jaw, ear outline; freckles/moles positions preserved.
3) Natural skin micro-texture visible; no beautification or symmetry fixes.
4) Reference canvas used; two horizontal panels; **zero** margins; single **invisible** center seam; background continuous; no bars/stripes/logos.

If any check fails, adjust only the failing aspects and **re-render** until all checks pass.

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
# aiogram_bot_template/services/enhancers/parent_visual_enhancer.py
import structlog
from typing import Optional

from aiogram_bot_template.data.settings import settings
from aiogram_bot_template.services.clients import factory as client_factory
from aiogram_bot_template.services.clients.mock_ai_client import MockAIClient

logger = structlog.get_logger(__name__)

# The prompt for the new parent visual representation enhancer model
_PARENT_VISUAL_ENHANCER_SYSTEM_PROMPT = """
You are Nano Banana (Gemini 2.5 Flash Image) operating as a specialized ID-consolidation module — InstantID / PhotoMaker / ID-Adapter style.

INPUT: Three portrait photos of the SAME person are attached to this prompt.

GOAL: Produce ONE photorealistic image that contains TWO side-by-side panels of that same person:
• LEFT panel — FRONT view (near-frontal), eyes open, relaxed & approachable expression, gentle micro-smile.
• RIGHT panel — SIDE view: right-profile ~85–95° (strict side), eyes open, natural posture.

IDENTITY CONSOLIDATION:
• Extract and fuse identity features from ALL THREE inputs; resolve disagreements by consensus to preserve stable facial geometry, skin texture, freckles/moles, eye shape/spacing, lip and nose contours, hairline.
• Do NOT beautify, age, slim, or stylize. Keep the real person.

HAIR & EXPRESSION (RELAXED):
• Natural hairstyle, lightly tousled is fine, but keep hair off the eyes.
• Soft, friendly micro-smile; no exaggerated grin.

CLEANUP & NORMALIZATION:
• Remove any headwear or eyewear; plausibly reconstruct previously occluded regions while keeping identity.
• Normalize exposure and white balance; eliminate color casts and harsh shadows for soft, even “daylight/studio” lighting across BOTH panels.
• Ignore transient artifacts (noise, compression, reflections, strong backlight).

FRAMING, LAYOUT & BACKGROUND:
• Single canvas in landscape or square orientation; split into TWO equal-width panels arranged HORIZONTALLY. Do NOT return two separate images.
• Optional thin neutral VERTICAL divider between panels; equal margins on all sides.
• Head-and-shoulders crop in both panels; subject centered.
• Background for BOTH panels: clean, plain, unobtrusive (light neutral gray/off-white or a very soft gradient). No text, logos, or decorative elements.

QUALITY:
• Photorealistic skin detail; sharp focus on the face; no painterly/cartoonish look.
• Consistent color science between panels; same person in both; no extra people or accessories.

REMEMBER:
• Use all three input photos strictly as identity references to CONSOLIDATE the same person into these two views.
• Output exactly ONE image composed of the two side-by-side panels (LEFT: FRONT, RIGHT: SIDE).
"""


async def get_parent_visual_representation(
    image_collage_url: str, role: str = "mother"
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
        model=config.model, image_url=image_collage_url
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
            image_urls=[image_collage_url],
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
# aiogram_bot_template/services/enhancers/eye_enhancer.py
import structlog
from typing import Optional

from aiogram_bot_template.data.settings import settings
from aiogram_bot_template.services.clients import factory as client_factory

logger = structlog.get_logger(__name__)

# --- MODIFIED PROMPT ---
# This prompt now explicitly instructs the model to frame the description
# as an inheritance from the "other" parent to avoid confusing the final image generator.
_EYE_ENHANCER_SYSTEM_PROMPT = """
You are an expert AI photo analyst and character artist. Your sole task is to analyze a photo of a parent and generate a concise, detailed, one-sentence description of their eyes, suitable for a child's portrait prompt.

**CRITICAL RULE 1: ANTI-SQUINT CORRECTION.**
If the parent in the photo is squinting, smiling widely, closing their eyes, or has partially obscured eyes for any reason (e.g., sun, laughter), you **MUST** ignore the squint/closure. Your task is to infer and describe their eyes in a **neutral, relaxed, fully open state.**

**CRITICAL RULE 2: EXPLICIT INHERITANCE CONTEXT.**
The final image generation model will see a photo of the *other* parent as its main reference. Therefore, your description **MUST** explicitly state that these eye features are inherited from the parent in *this* photo, to override the main reference.

Your description must detail the eye's inherent **shape** (e.g., 'almond-shaped', 'round', 'upturned', 'deep-set') and their precise **color and pattern** (e.g., 'deep chocolate brown with faint lighter flecks', 'bright sapphire blue with a dark limbal ring', 'hazel green with a golden central heterochromia').

**OUTPUT FORMAT:**
- A single, descriptive sentence.
- Do not add labels, explanations, or markdown.
- **Example:** "The child inherits the *other parent's* eyes: deep-set and almond-shaped, with a vibrant iris color of moss green and a subtle, dark limbal ring."
"""


async def get_eye_description(
    non_resemblance_parent_url: str,
) -> Optional[str]:
    """
    Analyzes a parent's photo and returns a detailed, corrected description of their eyes.
    This function intelligently handles cases where the parent is squinting and explicitly
    frames the description as an inheritance from the "other" parent.

    Args:
        non_resemblance_parent_url: The URL of the parent whose eyes are to be described.

    Returns:
        A single string describing the eyes, or None on failure.
    """
    log = logger.bind(model=settings.prompt_enhancer.model, image_url=non_resemblance_parent_url)
    try:
        client = client_factory.get_ai_client(settings.prompt_enhancer.client)
        log.info("Requesting eye description from vision model.")

        user_prompt_text = "Analyze the person in this photo and generate the eye description based on the system prompt rules."

        response = await client.chat.completions.create(
            model=settings.prompt_enhancer.model,
            messages=[
                {"role": "system", "content": _EYE_ENHANCER_SYSTEM_PROMPT},
                {"role": "user", "content": [
                    {"type": "text", "text": user_prompt_text},
                    {"type": "image_url", "image_url": {"url": non_resemblance_parent_url}, "detail": "high"},
                ]},
            ],
            max_tokens=150,
            temperature=0.3,
        )
        response_text = response.choices[0].message.content
        if not response_text:
            log.warning("Eye enhancer returned an empty response.")
            return None

        log.info("Successfully received eye description.", description=response_text.strip())
        return response_text.strip()

    except Exception:
        log.exception("An error occurred during eye description generation.")
        return None
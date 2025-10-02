# aiogram_bot_template/services/enhancers/hairstyle_enhancer.py
import structlog
from typing import List, Optional

from aiogram_bot_template.data.settings import settings
from aiogram_bot_template.services.clients import factory as client_factory
from aiogram_bot_template.data.constants import ChildAge, ChildGender

logger = structlog.get_logger(__name__)

_HAIRSTYLE_ENHANCER_SYSTEM_PROMPT = """
You are an expert AI stylist specializing in children's hair. Your task is to generate a list of creative, distinct, and age-appropriate hairstyle descriptions for a child's portrait.

**CRITICAL RULES:**
1.  **DO NOT MENTION HAIR COLOR.** The color will be determined by the main image generation model based on a parent's photo. Your description must focus exclusively on the **style, texture, and cut**.
2.  The descriptions must be concise, forming a single descriptive phrase or a short sentence.
3.  The styles must be appropriate for the specified age and gender.
4.  Each description in the list must be unique and offer a different visual idea.
5.  Output only the raw text description, without any labels, numbering, or markdown.

**Age and Gender Context:**
-   **Age:** {child_age_str}
-   **Gender:** {child_gender_str}

**Example Output for a 7-year-old girl (if you were asked for 3 styles):**
A neat, high ponytail tied with a simple ribbon, with a few playful wisps framing the face.
Soft, natural waves falling just past the shoulders, parted to the side.
Two tidy French braids starting from the crown and going all the way down.

**Example Output for a 2-year-old boy (if you were asked for 2 styles):**
A soft, slightly messy crop of fine hair with a gentle fringe over the forehead.
Neatly combed to the side, looking classic and smart.
"""

def _get_age_str(age_value: str) -> str:
    """Converts age enum value to a human-readable string."""
    try:
        age_enum = ChildAge(age_value)
        if age_enum == ChildAge.INFANT:
            return "infant or toddler (1-3 years)"
        if age_enum == ChildAge.CHILD:
            return "young child (5-7 years)"
        if age_enum == ChildAge.PRETEEN:
            return "teenager (9-11 years)"
    except ValueError:
        return "child" # Fallback
    return "child"

async def get_hairstyle_descriptions(
    num_hairstyles: int,
    child_age: str,
    child_gender: str
) -> Optional[List[str]]:
    """
    Generates a list of N distinct hairstyle descriptions for a child.

    Args:
        num_hairstyles: The number of unique hairstyle descriptions to generate.
        child_age: The age category of the child (using ChildAge enum values).
        child_gender: The gender of the child (using ChildGender enum values).

    Returns:
        A list of hairstyle description strings, or None on failure.
    """
    if num_hairstyles <= 0:
        return []

    log = logger.bind(model=settings.text_enhancer.model, num_hairstyles=num_hairstyles, age=child_age, gender=child_gender)
    try:
        client = client_factory.get_ai_client(settings.text_enhancer.client)
        log.info("Requesting hairstyle descriptions from language model.")

        age_str = _get_age_str(child_age)
        gender_str = "girl" if child_gender == ChildGender.GIRL.value else "boy"

        system_prompt = _HAIRSTYLE_ENHANCER_SYSTEM_PROMPT.format(
            child_age_str=age_str,
            child_gender_str=gender_str
        )

        user_prompt = f"Please generate {num_hairstyles} distinct hairstyle descriptions based on the system prompt rules."

        response = await client.chat.completions.create(
            model=settings.text_enhancer.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=150 * num_hairstyles,
            temperature=0.8, # Higher temperature for more creativity
            n=1,
        )
        response_text = response.choices[0].message.content
        if not response_text:
            log.warning("Hairstyle enhancer returned an empty response.")
            return None

        # Split the response into a list of descriptions, cleaning up any extra whitespace or empty lines
        hairstyles = [line.strip() for line in response_text.split('\n') if line.strip()]

        if not hairstyles:
            log.warning("Could not parse any hairstyles from the response.", response=response_text)
            return None

        log.info("Successfully received hairstyle descriptions.", count=len(hairstyles), hairstyles=hairstyles)
        return hairstyles

    except Exception:
        log.exception("An error occurred during hairstyle description generation.")
        return None
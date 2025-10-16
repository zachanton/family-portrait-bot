# aiogram_bot_template/services/enhancers/child_prompt_enhancer.py
import json
import structlog
from typing import List, Optional

from pydantic import BaseModel, Field

from aiogram_bot_template.data.settings import settings
from aiogram_bot_template.services.clients import factory as client_factory
from aiogram_bot_template.data.constants import ChildAge, ChildGender

logger = structlog.get_logger(__name__)


# --- Pydantic Models for Structured LLM Output ---

class ParentalFeatureAnalysis(BaseModel):
    """Stores the analyzed hair, eye color, skin tone, and ethnicity for both parents and the derived child."""
    mother_hair_color: str = Field(..., description="A short, descriptive string of the mother's hair color. Must not mention hair style.")
    mother_eye_color: str = Field(..., description="A short, descriptive string of the mother's biological eye color. Must not mention glasses.")
    father_hair_color: str = Field(..., description="A short, descriptive string of the father's hair color. Must not mention hair style.")
    father_eye_color: str = Field(..., description="A short, descriptive string of the father's biological eye color. Must not mention glasses.")
    child_skin_tone_and_ethnicity_description: str = Field(
        ...,
        description="A short, descriptive string describing a plausible genetic blend of the parents' skin tones and undertones. This field must NOT mention hair or eye color or facial traits."
    )

class ChildCreativeVariation(BaseModel):
    """Stores the creative, non-pigmentation features for one child variation."""
    hairstyle_description: str = Field(..., description="A concise, creative, age-appropriate hairstyle description (style/texture/cut only, NO color).")

class ChildFeatureDetails(BaseModel):
    """The complete structured response from the LLM, containing both parent analysis and child creative variations."""
    parental_analysis: ParentalFeatureAnalysis
    child_variations: List[ChildCreativeVariation]


# --- System Prompt for the LLM ---

# --- UPDATED: Enhanced system prompt with PART 3 for generating universal resemblance blocks ---
_CHILD_FEATURE_SYSTEM_PROMPT = """
You are an expert AI geneticist and character artist. Your mission is to analyze a 2-panel reference image of two parents and generate a structured JSON object containing a detailed analysis of the parents and creative variations for their child.

**INPUTS YOU WILL RECEIVE:**
- A 2-panel image: left is the Mother, right is the Father.
- Parameters: child's age, gender, and the number of child variations needed.

**GOAL:**
Produce a single, valid JSON object that strictly adheres to the schema. The object has three main parts you must generate.

**PART 1: `parental_analysis` (Strict Observation & Genetic Blending)**
- Meticulously analyze the Mother's and Father's photos.
- For `mother_hair_color`, `mother_eye_color`, `father_hair_color`, and `father_eye_color`, provide a precise and descriptive string.
    - **For eye color:** Focus ONLY on the biological color of the iris (e.g., 'deep chocolate brown', 'icy blue'). **Strictly forbid** any mention of glasses, reflections, or contact lenses.
    - If eyes are closed, make a best-guess based on other images or ethnicity cues.
- For `child_skin_tone_and_ethnicity_description`, write a single, descriptive paragraph of 30-60 words focusing ONLY on a plausible genetic blend of skin and ancestry.
    - **STRICTLY FORBIDDEN:** Do NOT mention hair color or eye color in this description.

**PART 2: `child_variations` (Creative Generation)**
- Generate a list containing the requested number of unique creative variations for the child.
- **`hairstyle_description`:**
    - Do **NOT** mention hair color. Focus only on style, texture, and cut.
    - Ensure the style is unique for each variation and is appropriate for the child's age and gender.

**OUTPUT FORMAT:**
- Respond with **JSON ONLY**. No extra text, explanations, or markdown.
- The JSON must strictly adhere to the schema provided.
"""

def _get_age_str(age_value: str) -> str:
    """Converts age enum value to a human-readable string for the prompt."""
    try:
        age_enum = ChildAge(age_value)
        if age_enum == ChildAge.INFANT:
            return "infant or toddler (1-3 years)"
        if age_enum == ChildAge.CHILD:
            return "young child (5-7 years)"
        if age_enum == ChildAge.PRETEEN:
            return "preteen (9-11 years)"
    except ValueError:
        return "child"
    return "child"


async def get_enhanced_child_features(
    parent_composite_url: str,
    num_variations: int,
    child_age: str,
    child_gender: str,
) -> Optional[ChildFeatureDetails]:
    """
    Generates a structured object containing analyzed parental features and creative
    variations for their child.

    Args:
        parent_composite_url: URL to the 2-panel image of both parents.
        num_variations: The number of unique child variations to generate.
        child_age: The age category of the child.
        child_gender: The gender of the child.

    Returns:
        A ChildFeatureDetails object, or None on failure.
    """
    config = settings.text_enhancer
    if not config.enabled:
        logger.warning("Child prompt enhancer is disabled in settings.")
        return None

    log = logger.bind(
        model=config.model,
        image_url=parent_composite_url,
        num_variations=num_variations
    )

    try:
        client = client_factory.get_ai_client(config.client)
        log.info("Requesting structured child features from vision model.")

        schema_definition = ChildFeatureDetails.model_json_schema()
        age_str = _get_age_str(child_age)
        gender_str = "girl" if child_gender == ChildGender.GIRL.value else "boy"

        user_prompt_text = (
            f"Please perform a parental analysis and generate {num_variations} unique creative variations for a {age_str} {gender_str}. "
            "Analyze the parents in the provided 2-panel photo. "
            "Return your analysis as a JSON object that strictly follows this schema:"
            f"\n\n```json\n{json.dumps(schema_definition, indent=2)}\n```"
        )

        response = await client.chat.completions.create(
            model=config.model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _CHILD_FEATURE_SYSTEM_PROMPT},
                {"role": "user", "content": [
                    {"type": "text", "text": user_prompt_text},
                    {"type": "image_url", "image_url": {"url": parent_composite_url}, "detail": "high"},
                ]},
            ],
            max_tokens=4096,
            temperature=0.9,
        )

        content = response.choices[0].message.content if response.choices else None
        if not content:
            log.warning("Child feature enhancer returned an empty response.")
            return None

        feature_details = ChildFeatureDetails.model_validate_json(content)
        log.info("Successfully received structured child features.",
                 parent_analysis=feature_details.parental_analysis.model_dump(),
                 variations_count=len(feature_details.child_variations))

        # Ensure we have enough creative variations, cycling if necessary
        if len(feature_details.child_variations) < num_variations:
            log.warning("LLM returned fewer creative variations than requested.",
                        requested=num_variations, returned=len(feature_details.child_variations))
            if feature_details.child_variations:
                cycled_variations = [feature_details.child_variations[i % len(feature_details.child_variations)] for i in range(num_variations)]
                feature_details.child_variations = cycled_variations

        return feature_details

    except Exception:
        log.exception("An error occurred during child prompt enhancement.")
        return None
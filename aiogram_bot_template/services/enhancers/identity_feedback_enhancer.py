# aiogram_bot_template/services/enhancers/identity_feedback_enhancer.py
import json
import structlog
from typing import Dict, Optional

from pydantic import BaseModel, Field, field_validator

from aiogram_bot_template.data.settings import settings
from aiogram_bot_template.services.clients import factory as client_factory

logger = structlog.get_logger(__name__)

# --- Pydantic Models for Structured Output ---

class FeatureFeedback(BaseModel):
    """Stores detailed feedback for a specific facial feature."""
    is_match: bool = Field(..., description="True if the feature is a perfect match, otherwise False.")
    feedback: str = Field(..., description="Detailed feedback on what to change if it's not a match, or 'Perfect match.' if it is.")

class IdentityFeedbackResponse(BaseModel):
    """The structured response from the identity feedback model."""
    similarity_score: float = Field(..., ge=0.0, le=1.0, description="A score from 0.0 (different person) to 1.0 (identical).")
    feedback_details: Dict[str, FeatureFeedback] = Field(..., description="Per-feature breakdown of similarity.")

    @field_validator("similarity_score")
    @classmethod
    def score_must_be_float(cls, v: float) -> float:
        if not isinstance(v, float):
            raise TypeError("similarity_score must be a float")
        return v

# --- System Prompt for the LLM ---

_IDENTITY_FEEDBACK_SYSTEM_PROMPT = """
You are an expert AI forensic artist and identity verification specialist. Your task is to perform a meticulous comparison between two images and provide structured, actionable feedback in JSON format.

**INPUT:**
- **Image A (Reference):** The ground truth. This is a 2x2 collage of the person whose identity must be replicated.
- **Image B (Candidate):** The generated image that attempts to replicate the identity from Image A.

**GOAL:**
Your output will be used to guide another AI model. You must identify every single deviation in the Candidate image (B) compared to the Reference (A) and provide precise instructions on how to fix it.

**EVALUATION CRITERIA:**

1.  **`similarity_score` (0.0 to 1.0):**
    - **1.0:** Perfect match. Indistinguishable from the reference, including all unique asymmetries and micro-expressions.
    - **0.9 - 0.99:** Near-perfect. Only minor, almost unnoticeable deviations in texture or subtle feature geometry.
    - **0.7 - 0.89:** Recognizably the same person, but with noticeable inaccuracies (e.g., nose is slightly thinner, jaw is softer, a key mole is missing).
    - **0.5 - 0.69:** Shares some resemblance but could be mistaken for a sibling or a heavily airbrushed version. Major features are altered.
    - **< 0.5:** A different person.

2.  **`feedback_details` (Per-Feature Analysis):**
    - For each feature listed below, you must compare Image A and Image B.
    - If they match perfectly, set `is_match` to `true` and `feedback` to "Perfect match."
    - If there's a discrepancy, set `is_match` to `false` and provide **specific, corrective feedback**.
    - **DO NOT** give vague advice. Be precise.
      - **Bad:** "The nose is wrong."
      - **Good:** "The candidate's nose is 10% narrower at the bridge than the reference. Widen the bridge and slightly increase the roundness of the nasal tip to match the reference."

**FEATURES TO ANALYZE:**
- `face_shape`: Overall head and face geometry.
- `eyes`: Shape, size, spacing, eyelid folds, and any asymmetry.
- `eyebrows`: Shape, thickness, arch, and position.
- `nose`: Bridge width, dorsal line straightness/curve, tip shape, and nostril size/flare.
- `mouth_and_lips`: Lip fullness ratio (upper vs. lower), shape of the Cupid's bow, and corner angle.
- `chin_and_jawline`: Chin shape (pointed, square, round) and jaw definition.
- `skin_and_texture`: Presence and location of moles, freckles, scars, and overall skin texture (e.g., pores). Ignore clothing and accessories.

**OUTPUT FORMAT:**
- Respond with **JSON ONLY**.
- The JSON must strictly adhere to the schema provided in the user prompt. No extra text or explanations.
"""

async def get_identity_feedback(
    reference_image_url: str,
    candidate_image_url: str,
) -> Optional[IdentityFeedbackResponse]:
    """
    Compares a candidate image against a reference collage and returns structured feedback
    on identity similarity using a vision-capable language model.

    Args:
        reference_image_url: The public URL to the original 2x2 collage.
        candidate_image_url: The public URL to the newly generated visual representation.

    Returns:
        An IdentityFeedbackResponse object containing the score and detailed feedback,
        or None if an error occurs.
    """
    config = settings.text_enhancer  # Use the same config as other text/vision enhancers
    if not config.enabled:
        logger.warning("Identity feedback enhancer is disabled in settings.")
        return None

    log = logger.bind(
        model=config.model,
        reference_url=reference_image_url,
        candidate_url=candidate_image_url
    )

    try:
        client = client_factory.get_ai_client(config.client)
        log.info("Requesting identity similarity feedback from vision model.")

        schema_definition = IdentityFeedbackResponse.model_json_schema()
        user_prompt_text = (
            "Analyze the two provided images (Image A: Reference, Image B: Candidate) "
            "based on the system prompt rules. Return your analysis as a JSON object that "
            f"strictly follows this schema:\n\n```json\n{json.dumps(schema_definition, indent=2)}\n```"
        )

        response = await client.chat.completions.create(
            model=config.model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _IDENTITY_FEEDBACK_SYSTEM_PROMPT},
                {"role": "user", "content": [
                    {"type": "text", "text": user_prompt_text},
                    {"type": "image_url", "image_url": {"url": reference_image_url}, "detail": "high"},
                    {"type": "image_url", "image_url": {"url": candidate_image_url}, "detail": "high"},
                ]},
            ],
            max_tokens=2048,
            temperature=0.1,
        )

        content = response.choices[0].message.content if response.choices else None
        if not content:
            log.warning("Identity feedback enhancer returned an empty response.")
            return None

        feedback_response = IdentityFeedbackResponse.model_validate_json(content)
        log.info(
            "Successfully received identity feedback.",
            score=feedback_response.similarity_score,
            details=feedback_response.model_dump()
        )
        return feedback_response

    except Exception:
        log.exception("An error occurred during identity feedback generation.")
        return None
# aiogram_bot_template/services/prompt_enhancer.py

import json
import structlog
from pydantic import BaseModel, Field
from aiogram_bot_template.data.settings import settings
from aiogram_bot_template.services.clients import factory as client_factory
from aiogram_bot_template.services.prompting.enhancer_prompt import PROMPT_ENHANCER_SYSTEM

logger = structlog.get_logger(__name__)


# --- NEW: Pydantic models for structured output ---

class EyesDetail(BaseModel):
    color: str = Field(description="The precise eye color. If ambiguous, state the possible range (e.g., 'blue or light grey').")
    shape: str = Field(description="Detailed eye shape (e.g., 'almond-shaped and slightly wide-set, with a visible upper eyelid crease').")

class NoseDetail(BaseModel):
    bridge: str = Field(description="Description of the nose bridge (dorsum), e.g., 'Narrow and straight'.")
    tip: str = Field(description="Description of the nose tip (apex), e.g., 'Small and slightly upturned'.")
    nostrils: str = Field(description="Description of the nostrils, e.g., 'Narrow'.")

class IdentityLock(BaseModel):
    overall_impression: str = Field(description="A brief, one-sentence summary of the person's core look and essence.")
    face_geometry: str = Field(description="Analysis of face shape, cheekbones, jawline, and chin.")
    eyes: EyesDetail
    eyebrows: str = Field(description="Description of eyebrow thickness, shape, and texture.")
    nose: NoseDetail
    lips: str = Field(description="Description of lip fullness (upper vs. lower), Cupid's bow, and smile.")
    skin: str = Field(description="Description of skin tone, undertone, and a command to retain all micro-details like freckles.")
    hair: str = Field(description="Description of hair style, color, texture, and length.")
    unique_details: str = Field(description="Any other unique details like moles, scars, or accessories.")

class CleanupInstructions(BaseModel):
    artifacts: str = Field(description="Instructions for removing artifacts like phones, hands, or bags.")
    seam: str = Field(description="Instruction for blending the vertical collage seam.")
    logos: str = Field(description="Instruction for removing any logos.")

class EnhancedPromptData(BaseModel):
    """The root model for the structured JSON output from the enhancer LLM."""
    person_a: IdentityLock = Field(description="Detailed forensic analysis of Person A (woman on the left).")
    person_b: IdentityLock = Field(description="Detailed forensic analysis of Person B (man on the right).")
    cleanup: CleanupInstructions

# --- END: Pydantic models ---


async def enhance_prompt(
    image_url: str,
    base_prompt: str,
) -> EnhancedPromptData | None:
    """
    Uses a vision-language model to generate structured data for enhancing a prompt.
    If the process fails, is disabled, or returns invalid data, it returns None.

    Args:
        image_url: The public URL of the composite image to analyze.
        base_prompt: The original, style-defining prompt (used for context).

    Returns:
        An EnhancedPromptData object on success, or None on failure.
    """
    if not settings.prompt_enhancer.enabled:
        logger.debug("Prompt enhancer is disabled in settings.")
        return None

    log = logger.bind(
        enhancer_model=settings.prompt_enhancer.model,
        image_url=image_url,
    )

    try:
        client = client_factory.get_ai_client(settings.prompt_enhancer.client)
        
        log.info("Requesting structured prompt data from vision model.")
        
        # We now provide the JSON schema in the prompt to guide the model
        schema_definition = EnhancedPromptData.model_json_schema()

        response = await client.chat.completions.create(
            model=settings.prompt_enhancer.model,
            # --- NEW: Enforcing JSON mode ---
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": PROMPT_ENHANCER_SYSTEM,
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": f"Analyze the provided image and generate a JSON object that strictly adheres to the following schema. The field descriptions in the schema are part of your instructions.\n\nSCHEMA:\n```json\n{json.dumps(schema_definition, indent=2)}\n```",
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": image_url,
                            },
                        },
                    ],
                },
            ],
            max_tokens=4096, # Increased token limit for potentially verbose JSON
            temperature=0.1,
        )

        response_text = response.choices[0].message.content
        if not response_text:
            log.warning("Prompt enhancer returned an empty response.")
            return None
        
        # --- NEW: Robust parsing and validation ---
        try:
            json_data = json.loads(response_text)
            validated_data = EnhancedPromptData.model_validate(json_data)
            log.info("Successfully received and validated structured prompt data.")
            return validated_data
        except (json.JSONDecodeError, Exception) as e:
            log.exception(
                "Failed to parse or validate JSON from enhancer model.",
                response_text=response_text,
                error=str(e)
            )
            return None

    except Exception:
        log.exception("An error occurred during prompt enhancement call.")
        return None

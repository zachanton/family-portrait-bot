# aiogram_bot_template/services/enhancers/identity_lock_enhancer.py
import json
import structlog
from pydantic import BaseModel, Field
from typing import Dict

from aiogram_bot_template.data.settings import settings
from aiogram_bot_template.services.clients import factory as client_factory

logger = structlog.get_logger(__name__)

# --- System prompt is now co-located with the logic that uses it ---
_PROMPT_ENHANCER_SYSTEM = """
ARTISTIC DIRECTIVE: You are an AI-to-AI feature extractor. Your purpose is to create concise, descriptive phrases for a downstream image generation AI. Your primary goal is **obsessive, detailed, and faithful identity preservation**.

GOAL: Analyze the provided composite portrait of two individuals (Person A left, Person B right). Generate a single, valid JSON object with descriptive phrases enabling high-fidelity likeness.

GUIDELINES:
1) BE CONCISE AND DESCRIPTIVE: For each feature, output a short phrase or clause, not a command. Example for 'face_geometry': "oval face with defined chin".
2) FOCUS ON UNIQUE DETAILS: Emphasize asymmetries, moles, freckles, stubble patterns, eyebrow thickness/shape, nose tip/bridge, lip fullness, eye color/shape, hair length/texture/part, jewelry. Avoid generic words like "normal" or "average".
3) **ACCURACY IS PARAMOUNT. DO NOT INTERPRET OR GUESS:** Describe only what is clearly visible. Pay extreme attention to critical identity markers:
    - **Eyebrow Shape:** Explicitly state if they are 'arched', 'straight', 'thick', 'thin'. Double-check this.
    - **Hair Part:** Explicitly state if it is a 'center part', 'side part', or 'no visible part'. Double-check this.
    - **Face Shape:** Use precise terms like 'oval', 'square', 'round', 'heart-shaped'.
4) REFERENCE AS TRUTH: Maintain natural skin texture (no idealization). Preserve age cues accurately.
5) COLOR & TEXTURE PRECISION: Use specific color words (e.g., "light brown", "reddish-brown") and texture terms (e.g., "light stubble", "shoulder-length wavy hair").
6) SAFETY & CLEANUP: If you notice seams/feathering/logos, mention them in `cleanup` succinctly.

YOUR SOLE TASK IS TO GENERATE A SINGLE, VALID JSON OBJECT THAT STRICTLY ADHERES TO THE PROVIDED SCHEMA. DO NOT OUTPUT ANYTHING ELSE.
"""


class IdentityLock(BaseModel):
    """Describes the key facial features of two individuals for identity preservation."""
    person_a_left: Dict[str, str]
    person_b_right: Dict[str, str]
    cleanup: str = Field(..., description="Instructions for fixing composite artifacts.")


async def get_identity_lock_data(image_url: str) -> str | None:
    """
    Analyzes a composite photo and returns a detailed JSON string of facial features
    for the group photo pipeline.
    """
    log = logger.bind(model=settings.prompt_enhancer.model, image_url=image_url)
    try:
        client = client_factory.get_ai_client(settings.prompt_enhancer.client)
        log.info("Requesting identity lock data from vision model.")

        schema_definition = IdentityLock.model_json_schema()
        user_prompt_text = (
            "Analyze the couple in the image and generate a detailed JSON object describing their "
            f"key facial features for identity preservation.\n\nSCHEMA:\n```json\n{json.dumps(schema_definition, indent=2)}\n```"
        )
        
        response = await client.chat.completions.create(
            model=settings.prompt_enhancer.model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _PROMPT_ENHANCER_SYSTEM},
                {"role": "user", "content": [
                    {"type": "text", "text": user_prompt_text},
                    {"type": "image_url", "image_url": {"url": image_url}},
                ]},
            ],
            max_tokens=1024,
            temperature=0.1,
        )
        response_text = response.choices[0].message.content
        if not response_text:
            log.warning("Identity lock enhancer returned an empty response.")
            return None
        
        validated_data = IdentityLock.model_validate_json(response_text)
        log.info("Successfully received and validated identity lock data.")
        return validated_data.model_dump_json(indent=2)

    except Exception:
        log.exception("An error occurred during identity lock data generation.")
        return None
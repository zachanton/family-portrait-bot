# aiogram_bot_template/services/prompt_enhancer.py
import json
import structlog
from pydantic import BaseModel, Field
from typing import Dict

from aiogram_bot_template.data.settings import settings
from aiogram_bot_template.services.clients import factory as client_factory
from aiogram_bot_template.services.prompting.enhancer_prompt import PROMPT_ENHANCER_SYSTEM

logger = structlog.get_logger(__name__)

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
                {"role": "system", "content": PROMPT_ENHANCER_SYSTEM},
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
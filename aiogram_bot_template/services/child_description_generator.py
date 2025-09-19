# aiogram_bot_template/services/child_description_generator.py
import json
import structlog
from pydantic import BaseModel, Field
from typing import List

from aiogram_bot_template.data.settings import settings
from aiogram_bot_template.services.clients import factory as client_factory
from aiogram_bot_template.services.prompting.enhancer_child_prompt import PROMPT_ENHANCER_CHILD_SYSTEM

logger = structlog.get_logger(__name__)

class ChildDescriptionResponse(BaseModel):
    descriptions: List[str] = Field(..., min_items=1)

async def get_child_descriptions(
    image_url: str,
    child_gender: str,
    child_age: str,
    child_resemblance: str,
    child_count: int
) -> List[str] | None:
    """
    Uses a vision-language model to generate 'n' detailed text descriptions of a potential child.
    """
    log = logger.bind(model=settings.prompt_enhancer.model, image_url=image_url)
    try:
        client = client_factory.get_ai_client(settings.prompt_enhancer.client)
        log.info("Requesting child descriptions from vision model.")

        system_prompt = PROMPT_ENHANCER_CHILD_SYSTEM.replace(
            "{{child_gender}}", child_gender
        ).replace("{{child_age}}", child_age).replace("{{child_resemblance}}", child_resemblance).replace("{{count}}", str(child_count))

        user_prompt_text = (
            f"Analyze the couple in the image. Generate {child_count} descriptions for a {child_age} {child_gender} "
            f"who resembles '{child_resemblance}'."
        )

        response = await client.chat.completions.create(
            model=settings.prompt_enhancer.model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": [
                    {"type": "text", "text": user_prompt_text},
                    {"type": "image_url", "image_url": {"url": image_url}},
                ]},
            ],
            max_tokens=2048,
            temperature=0.8,
        )

        response_text = response.choices[0].message.content
        if not response_text:
            log.warning("Child description generator returned an empty response.")
            return None

        validated_data = ChildDescriptionResponse.model_validate_json(response_text)
        
        if len(validated_data.descriptions) < child_count:
            log.warning("Generator returned fewer descriptions than requested.", 
                        expected=child_count, got=len(validated_data.descriptions))
        
        log.info("Successfully received and validated child descriptions.")
        return validated_data.descriptions

    except Exception:
        log.exception("An error occurred during child description generation.")
        return None
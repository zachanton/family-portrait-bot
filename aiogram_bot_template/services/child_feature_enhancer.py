# aiogram_bot_template/services/child_feature_enhancer.py
import json
import structlog
from pydantic import BaseModel
from typing import List

from aiogram_bot_template.data.settings import settings
from aiogram_bot_template.services.clients import factory as client_factory
from aiogram_bot_template.services.prompting.enhancer_child_prompt import PROMPT_ENHANCER_CHILD_SYSTEM

logger = structlog.get_logger(__name__)

# Новая Pydantic-модель, соответствующая новой схеме в промпте
class ChildGenerationHints(BaseModel):
    genetic_guidance: str
    facial_structure_notes: str
    distinguishing_features: str

# Функция теперь возвращает этот объект, а не список строк
async def get_child_generation_hints(
    image_url: str,
    child_gender: str,
    child_age: str,
    child_resemblance: str,
) -> ChildGenerationHints | None:
    """
    Uses a vision-language model to generate structured genetic hints for creating a child's portrait.
    """
    log = logger.bind(model=settings.prompt_enhancer.model, image_url=image_url)
    try:
        client = client_factory.get_ai_client(settings.prompt_enhancer.client)
        log.info("Requesting child generation hints from vision model.")

        # Промпт теперь не требует child_count
        system_prompt = PROMPT_ENHANCER_CHILD_SYSTEM.replace(
            "{{child_gender}}", child_gender
        ).replace("{{child_age}}", child_age).replace("{{child_resemblance}}", child_resemblance)

        user_prompt_text = (
            f"Analyze the couple in the image. Generate genetic and feature hints for a {child_age} {child_gender} "
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
            temperature=0.7, # Можно немного повысить креативность для подсказок
        )

        response_text = response.choices[0].message.content
        if not response_text:
            log.warning("Child hint generator returned an empty response.")
            return None

        # Валидируем по новой модели
        validated_data = ChildGenerationHints.model_validate_json(response_text)
        
        log.info("Successfully received and validated child generation hints.")
        return validated_data

    except Exception:
        log.exception("An error occurred during child hint generation.")
        return None
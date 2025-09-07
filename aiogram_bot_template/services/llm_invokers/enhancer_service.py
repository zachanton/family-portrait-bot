# aiogram_bot_template/services/llm_invokers/enhancer_service.py
import json
import asyncio # --- NEW IMPORT ---
from typing import Any

import structlog
from pydantic import BaseModel, ValidationError

from aiogram_bot_template.data.enums import AiFeature
from aiogram_bot_template.services.clients import factory as ai_client_factory
# --- NEW IMPORT ---
from aiogram_bot_template.services.google_sheets_logger import GoogleSheetsLogger


logger = structlog.get_logger(__name__)


class PromptEnhancerService:
    """A dedicated service for executing prompt blueprints using a vision model."""

    def __init__(self) -> None:
        self.client, self.model = ai_client_factory.get_ai_client_and_model(
            feature=AiFeature.PROMPT_ENHANCER
        )

    async def generate_structured_prompt(
        self,
        system_prompt: str,
        user_content: list[dict[str, Any]],
        output_model: type[BaseModel]
    ) -> BaseModel:
        """
        A universal method to generate a validated Pydantic object from an LLM
        based on a system prompt, user content, and a desired output model.
        """
        log = logger.bind(model=self.model)

        messages = [
            {"role": "user", "content": [{"type": "text", "text": system_prompt}, *user_content]}
        ]

        output_schema = output_model.model_json_schema()

        try:
            log.info("Sending structured prompt generation request to vision model")
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.2,
                max_tokens=1024,
                response_format={"type": "json_schema", "json_schema": {
                    "name": "structured_prompt_response",
                    "schema": output_schema,
                    "strict": True
                }},
            )
            response_content = response.choices[0].message.content
            log.info("Received structured prompt response", response=response_content)

            # Validate the JSON response against the provided Pydantic model
            validated_data = output_model.model_validate(json.loads(response_content))
            
            # --- ADDED LOGGING CALL ---
            asyncio.create_task(
                GoogleSheetsLogger().log_prompt_enhancement(
                    user_content=user_content,
                    system_prompt=system_prompt,
                    model_name=self.model,
                    result_model=validated_data,
                )
            )
            
            return validated_data

        except (json.JSONDecodeError, ValidationError, AttributeError, IndexError) as e:
            log.error("LLM failed to return valid JSON for structured prompt.", error=str(e), schema=output_schema)
            raise ValueError("Failed to generate a valid structured prompt from the LLM.") from e

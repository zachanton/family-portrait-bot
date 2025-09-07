# File: aiogram_bot_template/dto/post_generation_context.py

from pydantic import BaseModel
from typing import Any
import json

from .facial_features import ImageDescription
from aiogram_bot_template.data.constants import GenerationType, SessionContextType


class GenerationContext(BaseModel):
    """
    A type-safe data transfer object for storing the necessary context in the database
    to resume a user's session from any generation.
    """
    parent_descriptions: dict[str, Any] | None = None
    child_description: ImageDescription | None = None
    
    # The scenario to show AFTER this generation is displayed.
    session_context: SessionContextType = SessionContextType.UNKNOWN


class PostGenerationContext(BaseModel):
    """
    A type-safe data transfer object for storing the necessary context in Redis
    to continue a user's session after a generation is complete (e.g., for editing).
    This is a short-lived bridge between the worker and the next step handlers.
    """
    request_id: int
    generation_id: int
    generation_type: GenerationType
    file_id: str
    unique_id: str
    context: GenerationContext

    @classmethod
    def from_db_record(cls, generation_record: dict) -> "PostGenerationContext":
        """
        Factory method to safely create an instance from a generation DB record.
        This is robust against context_metadata being a string or a dict.
        """
        raw_context = generation_record.get("context_metadata")
        context_data = {}

        if isinstance(raw_context, str):
            try:
                context_data = json.loads(raw_context)
            except json.JSONDecodeError:
                pass
        elif isinstance(raw_context, dict):
            context_data = raw_context

        return cls(
            request_id=generation_record["request_id"],
            generation_id=generation_record["id"],
            generation_type=GenerationType(generation_record["type"]),
            file_id=generation_record["result_file_id"],
            unique_id=generation_record["result_image_unique_id"],
            context=GenerationContext.model_validate(context_data)
        )
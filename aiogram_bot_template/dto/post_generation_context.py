# aiogram_bot_template/dto/post_generation_context.py
from pydantic import BaseModel
from aiogram_bot_template.data.constants import GenerationType


class PostGenerationContext(BaseModel):
    """
    A type-safe data transfer object for storing context in Redis
    to continue a user's session after a generation is complete.
    """
    request_id: int
    generation_id: int
    generation_type: GenerationType
    file_id: str
    unique_id: str
# aiogram_bot_template/services/clients/mock_ai_client.py
from __future__ import annotations
import asyncio
import io
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import structlog
from pydantic import BaseModel
from PIL import Image

# Import GenerationType for context
from aiogram_bot_template.data.constants import GenerationType

logger = structlog.get_logger(__name__)

_ASSETS_DIR = Path(__file__).parent.parent.parent / "assets"/ "pair0"
_MOCK_FAMILY_IMAGE_PATH = _ASSETS_DIR / "mock_family.jpg"
_MOCK_PAIR_IMAGE_PATH = _ASSETS_DIR / "mock_pair.png"
_MOCK_CHILD_IMAGE_PATH = _ASSETS_DIR / "mock_son1.png"

_MOCK_MOM_VISUAL_IMAGE_PATH = _ASSETS_DIR / "mock_mom_front_side.png"
_MOCK_DAD_VISUAL_IMAGE_PATH = _ASSETS_DIR / "mock_dad_front_side.png"


class MockAIClientResponse(BaseModel):
    image_bytes: bytes
    content_type: str = "image/png"
    response_payload: dict[str, Any]
    class Config:
        arbitrary_types_allowed = True


class _MockImagesNamespace:
    @staticmethod
    async def generate(**kwargs: Any) -> MockAIClientResponse:
        logger.info("MOCK Images: Simulating final image generation...")
        await asyncio.sleep(1)

        generation_type = kwargs.get("generation_type")
        role = kwargs.get("role")
        
        image_path = None
        fallback_color = "red" # Default fallback color

        # 1. Prioritize the 'role' parameter to identify parent visual generation,
        # as this call doesn't use a standard GenerationType. This is more robust
        # than checking for substrings in the prompt.
        if role == "mother":
            image_path = _MOCK_MOM_VISUAL_IMAGE_PATH
            fallback_color = "purple"
            logger.info("MOCK Images: Using mock mother visual representation (detected via role).")
        elif role == "father":
            image_path = _MOCK_DAD_VISUAL_IMAGE_PATH
            fallback_color = "orange"
            logger.info("MOCK Images: Using mock father visual representation (detected via role).")
        
        # 2. If it's not a parent visual, use the explicit generation_type.
        elif generation_type == GenerationType.CHILD_GENERATION.value:
            image_path = _MOCK_CHILD_IMAGE_PATH
            fallback_color = "lightblue"
            logger.info("MOCK Images: Using mock child image.")
        
        elif generation_type in [GenerationType.FAMILY_PHOTO.value]:
            image_path = _MOCK_FAMILY_IMAGE_PATH
            fallback_color = "darkgreen"
            logger.info("MOCK Images: Using mock family image for this generation type.", type=generation_type)
        
        elif generation_type in [GenerationType.PAIR_PHOTO.value]:
            image_path = _MOCK_PAIR_IMAGE_PATH
            fallback_color = "darkblue"
            logger.info("MOCK Images: Using mock pair image for this generation type.", type=generation_type)

        # 3. Default to the family/group photo as a safe fallback.
        else:
            image_path = _MOCK_FAMILY_IMAGE_PATH
            fallback_color = "gray"
            logger.warning(
                "MOCK Images: Could not determine specific image. Using default family image.",
                gen_type=generation_type,
                role=role
            )

        try:
            image_bytes = image_path.read_bytes()
        except FileNotFoundError:
            logger.error("Mock image asset not found!", path=str(image_path))
            # Create a fallback image if the asset is missing
            img = Image.new("RGB", (1024, 1024), fallback_color)
            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            image_bytes = buffer.getvalue()

        return MockAIClientResponse(
            image_bytes=image_bytes,
            response_payload={"mock_data": True, "seed": 12345, "url": f"file://{image_path}"}
        )


class MockAIClient:
    def __init__(self, **_kwargs: Any) -> None:
        self.images = _MockImagesNamespace()
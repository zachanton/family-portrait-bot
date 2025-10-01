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

_ASSETS_DIR = Path(__file__).parent.parent.parent / "assets"
_MOCK_FAMILY_IMAGE_PATH = _ASSETS_DIR / "family.jpg"
_MOCK_CHILD_IMAGE_PATH = _ASSETS_DIR / "mock_child_11.jpg"
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
        prompt = kwargs.get("prompt", "")
        # --- NEW: Explicitly get the role ---
        role = kwargs.get("role")
        
        image_path = None
        fallback_color = "red" # Default fallback color

        # 1. Check for the specific prompt of the parent visual enhancer first.
        if "ID-consolidation" in prompt or "ID-refinement" in prompt:
            # --- REVISED LOGIC: Use the 'role' parameter directly ---
            if role == "mother":
                image_path = _MOCK_MOM_VISUAL_IMAGE_PATH
                fallback_color = "purple"
                logger.info("MOCK Images: Using mock mother visual representation image.")
            elif role == "father":
                image_path = _MOCK_DAD_VISUAL_IMAGE_PATH
                fallback_color = "orange"
                logger.info("MOCK Images: Using mock father visual representation image.")
            else:
                # --- NEW: Safety fallback to prevent UnboundLocalError ---
                image_path = _MOCK_FAMILY_IMAGE_PATH
                fallback_color = "gray"
                logger.warning("MOCK: ID-consolidation prompt detected but role was not specified. Using default family image.")
        
        # 2. Check for the child generation type.
        elif generation_type == GenerationType.CHILD_GENERATION.value:
            image_path = _MOCK_CHILD_IMAGE_PATH
            fallback_color = "lightblue"
            logger.info("MOCK Images: Using mock child image.")
        
        # 3. Default to the family/group photo.
        else:
            image_path = _MOCK_FAMILY_IMAGE_PATH
            fallback_color = "darkgreen"
            logger.info("MOCK Images: Using standard mock family image.")

        try:
            # This line will now always have a valid image_path
            image_bytes = image_path.read_bytes()
        except FileNotFoundError:
            logger.error("Mock image asset not found!", path=image_path)
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
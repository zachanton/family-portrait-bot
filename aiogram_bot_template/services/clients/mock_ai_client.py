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

# --- NEW: Import GenerationType for context ---
from aiogram_bot_template.data.constants import GenerationType

logger = structlog.get_logger(__name__)

# --- NEW: Define paths to both mock images ---
_ASSETS_DIR = Path(__file__).parent.parent.parent / "assets"
_MOCK_FAMILY_IMAGE_PATH = _ASSETS_DIR / "family.jpg"
_MOCK_CHILD_IMAGE_PATH = _ASSETS_DIR / "child_2.jpg"


class MockAIClientResponse(BaseModel):
    image_bytes: bytes
    content_type: str = "image/png"
    response_payload: dict[str, Any]
    class Config:
        arbitrary_types_allowed = True


class _MockImagesNamespace:
    # --- MODIFIED: The method now checks the generation type ---
    @staticmethod
    async def generate(**kwargs: Any) -> MockAIClientResponse:
        logger.info("MOCK Images: Simulating final image generation...")
        await asyncio.sleep(1)

        # Determine which mock image to use based on the context
        generation_type = kwargs.get("generation_type")
        
        if generation_type == GenerationType.CHILD_GENERATION.value:
            image_path = _MOCK_CHILD_IMAGE_PATH
            fallback_color = "lightblue"
            logger.info("MOCK Images: Using mock child image.")
        else: # Default to family/group photo
            image_path = _MOCK_FAMILY_IMAGE_PATH
            fallback_color = "darkgreen"
            logger.info("MOCK Images: Using standard mock family image.")

        try:
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
# aiogram_bot_template/services/clients/mock_ai_client.py
from __future__ import annotations
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, io

import structlog
from pydantic import BaseModel
from PIL import Image

from aiogram_bot_template.dto.facial_features import ImageDescription


logger = structlog.get_logger(__name__)

# Define paths for both standard and family portrait mock images
_ASSETS_DIR = Path(__file__).parent.parent.parent / "assets"
_MOCK_IMAGE_PATH = _ASSETS_DIR / "mock_image.png"
_MOCK_FAMILY_IMAGE_PATH = _ASSETS_DIR / "mock_family.jpg"


def _sanitize_messages_for_logging(messages: list) -> list:
    """Replaces large base64 image data in messages with a placeholder for clean logging."""
    sanitized_messages = []
    for msg in messages:
        new_msg = msg.copy()
        content = new_msg.get("content")
        
        if isinstance(content, list):
            new_content = []
            for part in content:
                if (
                    isinstance(part, dict) and
                    part.get("type") == "image_url" and
                    "image_url" in part and
                    isinstance(part["image_url"], dict) and
                    part["image_url"].get("url", "").startswith("data:")
                ):
                    new_part = part.copy()
                    new_part["image_url"] = {"url": "<base64_image_data_truncated>"}
                    new_content.append(new_part)
                else:
                    new_content.append(part)
            new_msg["content"] = new_content
            
        sanitized_messages.append(new_msg)
    return sanitized_messages


class MockAIClientResponse(BaseModel):
    image_bytes: bytes
    content_type: str = "image/png"
    response_payload: dict[str, Any]
    class Config:
        arbitrary_types_allowed = True


class MockMessage(BaseModel):
    content: str


class MockChoice(BaseModel):
    message: MockMessage


class MockCompletionResponse(BaseModel):
    choices: list[MockChoice]


_MOCK_PROFILE_1 = ImageDescription(
    gender="female",
    ethnicity="Caucasian",
    eyes={"color": "blue", "shape": "almond", "eyelid_type": "double eyelid"},
    hair={"color": "blonde", "texture": "wavy", "length": "long"},
    facial_structure={"face_shape": "oval", "nose_shape": "straight", "lip_shape": "full", "jawline": "soft", "cheekbones": "subtle", "chin_shape": "pointed", "eyebrows_shape": "arched"},
    skin={"tone": "fair", "freckles": False, "dimples": True},
    accessories={"has_glasses": False, "has_earrings": True, "has_hat": False, "has_necklace": False}
)

_MOCK_PROFILE_2 = ImageDescription(
    gender="male",
    ethnicity="Latino",
    eyes={"color": "green", "shape": "round", "eyelid_type": "double eyelid"},
    hair={"color": "brunette", "texture": "straight", "length": "short"},
    facial_structure={"face_shape": "square", "nose_shape": "roman", "lip_shape": "thin", "jawline": "sharp", "cheekbones": "prominent", "chin_shape": "square", "eyebrows_shape": "straight"},
    skin={"tone": "olive", "freckles": True, "dimples": False},
    accessories={"has_glasses": False, "has_earrings": False, "has_hat": True, "has_necklace": False}
)


class _MockAsyncCompletions:
    def __init__(self) -> None:
        """This class no longer needs to be initialized with model-specific handlers."""

    async def create(self, model: str, messages: list, **_kwargs: Any) -> MockCompletionResponse:
        """
        Determines the type of mock response needed by inspecting the prompt content,
        making it robust against model name collisions in mock configurations.
        """
        sanitized_messages_for_log = _sanitize_messages_for_logging(messages)
        logger.info(
            "MOCK ChatCompletions: Received request",
            model=model,
            messages=sanitized_messages_for_log
        )

        prompt_text = ""
        try:
            content_list = messages[-1].get("content", [])
            if isinstance(content_list, list):
                for part in content_list:
                    if isinstance(part, dict) and part.get("type") == "text":
                        prompt_text = part.get("text", "")
                        break
            elif isinstance(content_list, str):
                prompt_text = content_list
        except (IndexError, KeyError, TypeError):
            logger.warning("Could not extract prompt text from messages for routing.")

        if "forensic facial analyst" in prompt_text:
            handler = self._handle_vision_analysis
        else:
            handler = self._handle_prompt_enhancer

        content = await handler(messages)
        message = MockMessage(content=content)
        choice = MockChoice(message=message)
        return MockCompletionResponse(choices=[choice])

    async def _handle_prompt_enhancer(self, messages: list) -> str:
        logger.info("MOCK: Simulating prompt enhancement...")
        await asyncio.sleep(0.5)

        user_prompt_text = "a cat"
        try:
            full_prompt = messages[0]["content"][0]["text"]
            user_prompt_text = full_prompt.split('**A.** Start with the basics: "')[-1].split('"')[0]
        except (IndexError, KeyError, TypeError):
            pass

        return json.dumps({
            "prompt": f"A photorealistic image of {user_prompt_text}, cinematic lighting, high detail."
        })

    async def _handle_vision_analysis(self, messages: list) -> str:
        """
        Simulates vision analysis, returning one of two predefined profiles.
        This version now sanitizes the URL for logging purposes.
        """
        await asyncio.sleep(0.5)

        image_url = ""
        try:
            content = messages[0].get("content", [])
            image_part = content[-1]
            if image_part.get("type") == "image_url":
                image_url = image_part.get("image_url", {}).get("url", "")
        except (IndexError, KeyError, AttributeError):
            pass
        
        log_url = image_url
        if log_url.startswith("data:"):
            log_url = f"<base64_image_data_len:{len(image_url)}>"
        
        if image_url and len(image_url) % 2 == 0:
            logger.info("MOCK: Returning Profile 1 (blue eyes) for URL", url=log_url)
            return _MOCK_PROFILE_1.model_dump_json()

        logger.info("MOCK: Returning Profile 2 (green eyes) for URL", url=log_url)
        return _MOCK_PROFILE_2.model_dump_json()

    async def _handle_default(self, messages: list) -> str:
        logger.warning("MOCK: No specific handler found, using default.", model=messages)
        return "This is a default mock response."


class _MockImagesNamespace:
    @staticmethod
    async def generate(**kwargs: Any) -> MockAIClientResponse:
        logger.info("MOCK Images: Simulating final image generation...")
        await asyncio.sleep(1)

        prompt = kwargs.get("prompt", "").lower()
        # Check for keywords related to group/family photos
        is_family_photo = any(keyword in prompt for keyword in ["family portrait", "cohesive", "group photo"])

        if is_family_photo:
            image_path = _MOCK_FAMILY_IMAGE_PATH
            fallback_color = "darkgreen"
            logger.info("MOCK Images: Detected family/group prompt, using family image.")
        else:
            image_path = _MOCK_IMAGE_PATH
            fallback_color = "purple"
            logger.info("MOCK Images: Using standard mock image.")

        try:
            image_bytes = image_path.read_bytes()
        except FileNotFoundError:
            logger.error("Mock image asset not found!", path=image_path)
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
        self.chat = SimpleNamespace(completions=_MockAsyncCompletions())
        self.images = _MockImagesNamespace()
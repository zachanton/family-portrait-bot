# aiogram_bot_template/services/clients/openrouter_client.py
from __future__ import annotations
import base64
import re
from typing import Any
import structlog
from pydantic import BaseModel

from aiogram_bot_template.data.settings import settings
from aiogram_bot_template.services.utils import http_client

logger = structlog.get_logger(__name__)

class OpenRouterClientResponse(BaseModel):
    """Standardized response from the OpenRouter generation client."""
    image_bytes: bytes
    content_type: str = "image/png"
    response_payload: dict

    class Config:
        arbitrary_types_allowed = True


def _parse_data_url(data_url: str) -> tuple[bytes, str]:
    """Parses a base64 data URL and returns the decoded bytes and mime type."""
    match = re.match(r"data:(image/.+);base64,(.+)", data_url)
    if not match:
        raise ValueError("Invalid data URL format")
    
    mime_type, b64_data = match.groups()
    image_bytes = base64.b64decode(b64_data)
    return image_bytes, mime_type


class _ImagesNamespace:
    """Handles the image generation logic for OpenRouter."""
    def __init__(self) -> None:
        if not settings.api_urls.openrouter_api_key:
            raise RuntimeError("Missing API key for OpenRouter. Set env var API_URLS__OPENROUTER_API_KEY.")
        
        self.api_url = f"{str(settings.api_urls.openrouter).strip('/')}/chat/completions"
        self.api_key = settings.api_urls.openrouter_api_key.get_secret_value()
        logger.info("OpenRouterClient initialized for image generation.")

    async def generate(self, **kwargs: Any) -> OpenRouterClientResponse:
        """
        Calls the OpenRouter chat completions endpoint with image generation modalities.
        """
        session = await http_client.session()
        
        model = kwargs.pop("model")
        prompt = kwargs.pop("prompt", "")
        image_urls = kwargs.pop("image_urls", [])
        
        if not image_urls:
            raise ValueError("image_urls are required for OpenRouter image generation.")

        # Build the content array as per OpenRouter's multimodal spec
        content = [{"type": "text", "text": prompt}]
        for url in image_urls:
            content.append({"type": "image_url", "image_url": {"url": url}})

        payload = {
            "model": model,
            "modalities": ["image", "text"], # Critical for enabling image output
            "messages": [{"role": "user", "content": content}],
            **kwargs # Pass any remaining parameters like temperature, seed, etc.
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        log = logger.bind(model=model, api_url=self.api_url)
        log.info("Sending request to OpenRouter Image Generation API")

        async with session.post(self.api_url, headers=headers, json=payload) as resp:
            resp.raise_for_status()
            result_json = await resp.json()

        try:
            # Navigate the specific response structure of OpenRouter
            img_data_url = result_json["choices"][0]["message"]["images"][0]["image_url"]["url"]
            image_bytes, content_type = _parse_data_url(img_data_url)

            return OpenRouterClientResponse(
                image_bytes=image_bytes,
                content_type=content_type,
                response_payload=result_json,
            )
        except (KeyError, IndexError, ValueError) as e:
            log.error(
                "Failed to parse image from OpenRouter response",
                response=result_json,
                error=str(e)
            )
            raise ValueError("OpenRouter returned an invalid or empty response for the image.") from e


class OpenRouterClient:
    def __init__(self, **_kwargs: Any) -> None:
        self.images = _ImagesNamespace()
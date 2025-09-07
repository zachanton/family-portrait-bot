# aiogram_bot_template/services/clients/local_ai_client.py
from __future__ import annotations
import base64
import logging
from typing import Any
import aiohttp
from aiogram_bot_template.data.settings import settings
import io
from PIL import Image

logger = logging.getLogger(__name__)

from pydantic import BaseModel


class LocalAIClientResponse(BaseModel):
    """Standardized response from the Local AI client."""
    image_bytes: bytes
    content_type: str = "image/png"
    response_payload: dict

    class Config:
        arbitrary_types_allowed = True


def _create_dummy_image_b64(width: int, height: int) -> str:
    """Creates a simple black image and returns it as a base64 string."""
    img = Image.new("RGB", (width, height), "black")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


class _ImagesNamespace:
    def __init__(self) -> None:
        self.api_url = f"{str(settings.api_urls.bentoml).strip('/')}/generate"
        self.provider = settings.local_model_provider
        logger.info(
            "BentoML client configured for URL: %s with provider: %s",
            self.api_url,
            self.provider
        )

    async def _download_image_b64_from_http_url(self, image_url: str) -> str | None:
        """Downloads an image from an HTTP/HTTPS URL and returns its base64 representation."""
        if not image_url:
            return None
        async with (
            aiohttp.ClientSession() as session,
            session.get(image_url) as response,
        ):
            response.raise_for_status()
            image_bytes = await response.read()
            return base64.b64encode(image_bytes).decode("utf-8")

    async def generate(self, **kwargs: Any) -> LocalAIClientResponse:
        """
        Calls the local BentoML service.
        It dynamically constructs the payload from kwargs, handling image URL to base64 conversion.
        """
        image_url = kwargs.get("image_url")
        image_b64 = None

        if image_url:
            if image_url.startswith("data:"):
                try:
                    _, b64_data = image_url.split(",", 1)
                    image_b64 = b64_data
                    logger.debug("Parsed image from data URL for warmup.")
                except ValueError:
                    logger.error("Invalid data URL format", url=image_url)
            else:
                image_b64 = await self._download_image_b64_from_http_url(image_url)

        # Start building the payload that goes inside the "batch"
        service_payload = kwargs.copy()

        # Add the base64 image using the correct key for the configured provider
        if image_b64:
            if self.provider == "flux":
                service_payload["reference_image_b64"] = image_b64
            elif self.provider == "qwen":
                service_payload["image_b64"] = image_b64

        # Clean up keys that are not part of the model's direct input
        service_payload.pop("model", None)
        service_payload.pop("image_url", None)

        # The local BentoML service expects a 'batch' list
        final_payload = {"batch": [service_payload]}

        try:
            logger.info(f"Sending request to BentoML service ({self.provider})...", payload=service_payload)
            async with (
                aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=610)) as session,
                session.post(self.api_url, json=final_payload) as response,
            ):
                response.raise_for_status()
                result_json = await response.json()
                first_image_b64 = result_json[0]

                image_bytes = base64.b64decode(first_image_b64)

                return LocalAIClientResponse(
                    image_bytes=image_bytes,
                    response_payload={"data": result_json}
                )

        except aiohttp.ClientError as e:
            logger.exception("Error while calling BentoML service")
            err = f"Failed to connect to BentoML service: {e}"
            raise ConnectionError(err) from e


class LocalGenerationClient:
    def __init__(self, **_kwargs: Any) -> None:
        self.images = _ImagesNamespace()


async def warmup(logger: logging.Logger | None = None) -> None:
    """Warms up the Bento service by sending a quick request."""
    try:
        client = LocalGenerationClient()
        provider = settings.local_model_provider

        if provider == "qwen":
            dummy_image_b64 = _create_dummy_image_b64(64, 64)
            # For Qwen, the image key is 'image_b64' inside the payload,
            # but the generate function expects 'image_url'. We use a data URL.
            await client.images.generate(
                prompt="warmup",
                image_url=f"data:image/png;base64,{dummy_image_b64}",
                width=64, height=64, seed=0, num_inference_steps=1, guidance_scale=1.0,
            )
        else:  # Default to flux
            # For FLUX, no image is needed for a simple prompt-only warmup
            await client.images.generate(
                prompt="warmup",
                width=1024, height=1024, seed=0, num_inference_steps=1, guidance_scale=1.0,
            )

        if logger:
            logger.info(f"Bento warmup for '{provider}' completed")
    except Exception as e:
        if logger:
            logger.warning("Bento warmup failed", exc_info=e)

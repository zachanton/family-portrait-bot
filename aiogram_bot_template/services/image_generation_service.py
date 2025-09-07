# File: aiogram_bot_template/services/image_generation_service.py
import imghdr
import time
from collections.abc import Awaitable, Callable
from typing import Any

import structlog
from aiogram import Bot
from aiogram.utils.i18n import gettext as _
from pydantic import BaseModel

from .clients.fal_async_client import FalAsyncClient

logger = structlog.get_logger(__name__)


def _guess_mime(data: bytes) -> str:
    kind = imghdr.what(None, data)
    if kind == "png":
        return "image/png"
    if kind in {"jpeg", "jpg"}:
        return "image/jpeg"
    if kind == "webp":
        return "image/webp"
    # fallback
    return "application/octet-stream"


class GenerationResult(BaseModel):
    """
    Standardized result from any generation client. Always contains a single image's data.
    """
    image_bytes: bytes
    content_type: str
    request_payload: dict
    response_payload: dict
    generation_time_ms: int

    class Config:
        arbitrary_types_allowed = True


async def generate_image_with_reference(
    request_payload: dict[str, Any],
    ai_client: Any,
    status_callback: Callable[[str], Awaitable[None]] | None = None,
) -> tuple[GenerationResult, None] | tuple[None, dict]:

    log = logger.bind(
        model=request_payload.get("model"),
    )
    metadata = {
        "request_payload": request_payload,
        "response_payload": None,
        "generation_time_ms": None,
    }
    start_time = time.monotonic()

    try:
        log.info("Sending request to Image Generation API", payload=request_payload)

        client_response: Any  # Can be dict or object

        if isinstance(ai_client, FalAsyncClient):
            model_id = request_payload.pop("model")

            async def fal_status_adapter(status: dict) -> None:
                if status_callback and (logs := status.get("logs")):
                    last_log = logs[-1].get("message", "")
                    if "warming up" in last_log.lower():
                        await status_callback(_("⚙️ Warming up the model..."))
                    elif "starting generation" in last_log.lower():
                        await status_callback(_("⏳ Generating..."))

            client_response = await ai_client.generate(
                model_id=model_id,
                arguments=request_payload,
                status_callback=fal_status_adapter,
            )
            metadata["response_payload"] = client_response.get("response")

        elif "status_callback" in ai_client.images.generate.__code__.co_varnames:
            client_response = await ai_client.images.generate(**request_payload, status_callback=status_callback)
            metadata["response_payload"] = client_response.response_payload
        else:
            client_response = await ai_client.images.generate(**request_payload)
            metadata["response_payload"] = client_response.response_payload

    except Exception as e:
        log.exception("An error occurred during image generation")
        metadata["generation_time_ms"] = int((time.monotonic() - start_time) * 1000)
        metadata["response_payload"] = {"error": str(e)}
        return None, metadata
    else:
        # We now use the consistently populated `metadata` dictionary for logging.
        log.info("Image generation successful", response_summary=str(metadata["response_payload"])[:200])
        metadata["generation_time_ms"] = int((time.monotonic() - start_time) * 1000)

        image_bytes: bytes | None = None
        content_type: str | None = None

        # Case 1: New FalAsyncClient (returns a dict)
        if isinstance(client_response, dict):
            log.debug("Adapting response from new FalAsyncClient.")
            image_bytes = client_response.get("image_bytes")
            content_type = client_response.get("content_type")
        # Case 2: New multi-image clients (like Gemini)
        elif hasattr(client_response, "image_bytes_list") and client_response.image_bytes_list:
            log.debug("Adapting response from multi-image client.", count=len(client_response.image_bytes_list))
            image_bytes = client_response.image_bytes_list[0]
            content_type = client_response.content_types[0]
        # Case 3: Old single-image clients (Local, Mock)
        elif hasattr(client_response, "image_bytes"):
            log.debug("Adapting response from single-image client.")
            image_bytes = client_response.image_bytes
            content_type = client_response.content_type

        if not image_bytes:
            log.error("Client response is missing image data.", response=client_response)
            if "response_payload" not in metadata or not metadata["response_payload"]:
                metadata["response_payload"] = {"error": "Invalid or empty response from AI client."}
            return None, metadata

        result = GenerationResult(
            image_bytes=image_bytes,
            content_type=content_type or "image/png",
            **metadata
        )
        return result, None


async def get_public_file_url(bot: Bot, file_id: str) -> str:
    file_info = await bot.get_file(file_id)
    return f"https://api.telegram.org/file/bot{bot.token}/{file_info.file_path}"

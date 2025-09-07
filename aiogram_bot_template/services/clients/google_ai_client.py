# aiogram_bot_template/services/clients/google_ai_client.py
from __future__ import annotations

import asyncio
import re
import time
import random
from io import BytesIO
from typing import Any
from collections.abc import Awaitable, Callable

import structlog
from PIL import Image
from pydantic import BaseModel
from google import genai
from google.genai import types, errors as genai_errors

from aiogram_bot_template.data.settings import settings
from aiogram_bot_template.services.utils import http_client

logger = structlog.get_logger(__name__)


class GoogleAIClientResponse(BaseModel):
    image_bytes_list: list[bytes]
    content_types: list[str]
    response_payload: dict
    class Config:
        arbitrary_types_allowed = True


class _TokenBucket:
    def __init__(self, rpm: int) -> None:
        self.rpm = max(1, rpm)
        self.tokens = float(self.rpm)
        self.updated = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self.updated
            self.tokens = min(self.rpm, self.tokens + elapsed * (self.rpm / 60.0))
            self.updated = now
            if self.tokens < 1.0:
                deficit = 1.0 - self.tokens
                await asyncio.sleep(deficit * 60.0 / self.rpm)
                self.tokens = 0.0
                self.updated = time.monotonic()
            self.tokens -= 1.0


def _extract_retry_seconds_from_error(e: Exception) -> float:
    s = str(e)
    m = re.search(r'"retryDelay"\s*:\s*"(\d+)s"', s)
    return float(m.group(1)) if m else 0.0


async def _download_image_bytes(url: str) -> tuple[bytes, str]:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    sess = await http_client.session()
    async with sess.get(url, headers=headers) as resp:
        resp.raise_for_status()
        data = await resp.read()
        try:
            with Image.open(BytesIO(data)) as im:
                mime = Image.MIME.get(im.format) or "image/png"
        except Exception:
            mime = "image/png"
    return data, mime


def _build_parts_from_images(images: list[tuple[bytes, str]], prompt: str) -> list[types.Part]:
    parts: list[types.Part] = [types.Part.from_text(text=prompt)]
    for data, mime in images:
        parts.append(types.Part.from_bytes(data=data, mime_type=mime))
    return parts


def _collect_image_parts_from_response(response) -> list[tuple[bytes, str]]:
    out: list[tuple[bytes, str]] = []
    for cand in getattr(response, "candidates", []) or []:
        content = getattr(cand, "content", None)
        if not content: continue
        for part in getattr(content, "parts", []) or []:
            inline = getattr(part, "inline_data", None)
            if inline and getattr(inline, "data", None):
                mime = getattr(inline, "mime_type", "image/png")
                out.append((inline.data, mime))
    return out


class _ImagesNamespace:
    def __init__(self) -> None:
        api_key = settings.api_urls.google_api_key
        if not api_key:
            raise RuntimeError("Missing API key for Google Gemini. Set env var API_URLS__GOOGLE_API_KEY.")
        self.genai_client = genai.Client(api_key=api_key.get_secret_value())
        self.async_models = self.genai_client.aio.models
        logger.info("Google Gemini client configured and authenticated.")
        rpm = getattr(settings, "google_genai_rpm_limit", 10)
        self._limiter = _TokenBucket(rpm=rpm)

    async def _status(self, cb: Callable[[str], Awaitable[None]] | None, msg: str) -> None:
        if cb:
            try: await cb(msg)
            except Exception: logger.warning("status_callback failed", msg=msg)

    async def generate(self, status_callback: Callable[[str], Awaitable[None]] | None = None, **kwargs: Any) -> GoogleAIClientResponse:
        model_name: str = kwargs.pop("model", "gemini-2.5-flash-image-preview")
        prompt: str = kwargs.get("prompt", "")
        image_urls: list[str] = kwargs.get("image_urls", []) or []
        if single_url := kwargs.get("image_url"):
            image_urls.append(single_url)

        await self._status(status_callback, f"Preparing request for {model_name}")
        images = await asyncio.gather(*[_download_image_bytes(u) for u in image_urls])
        parts = _build_parts_from_images(list(images), prompt)
        contents = parts or [types.Part.from_text(text=prompt)]
        cfg = types.GenerateContentConfig(temperature=kwargs.get("temperature", 0.8), seed=kwargs.get("seed"))

        max_retries = 5
        for attempt in range(max_retries):
            await self._limiter.acquire()
            try:
                await self._status(status_callback, "Calling Gemini API...")
                response = await self.async_models.generate_content(model=model_name, contents=contents, config=cfg)
                images_out = _collect_image_parts_from_response(response)
                if not images_out:
                    reason = "UNKNOWN"
                    if response.candidates: reason = response.candidates[0].finish_reason.name
                    raise ValueError(f"Gemini API returned no image data. Finish reason: {reason}")

                return GoogleAIClientResponse(
                    image_bytes_list=[b for b, _ in images_out],
                    content_types=[m for _, m in images_out],
                    response_payload={"text": getattr(response, "text", "")},
                )
            except genai_errors.APIError as e:
                is_rate_limit = "RESOURCE_EXHAUSTED" in str(e) or "429" in str(e)
                if is_rate_limit and attempt < max_retries - 1:
                    delay = max(1.0, _extract_retry_seconds_from_error(e)) * (2 ** attempt) + random.uniform(0, 1)
                    await self._status(status_callback, f"Rate limited. Retrying in {delay:.1f}s...")
                    await asyncio.sleep(delay)
                    continue
                logger.exception("Gemini API Error after retries or for a non-retriable reason.")
                raise e
        raise RuntimeError("Failed to get a response from Gemini after all retries.")


class GoogleAIClient:
    def __init__(self, **_kwargs: Any) -> None:
        self.images = _ImagesNamespace()

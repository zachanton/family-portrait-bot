# aiogram_bot_template/services/clients/google_ai_client.py
from __future__ import annotations
import asyncio
import json
from typing import Any, Iterable, List
from collections.abc import Awaitable, Callable
from io import BytesIO

import structlog
from pydantic import BaseModel
from PIL import Image as PILImage  # only for optional local save/debug

from aiogram_bot_template.data.settings import settings
from aiogram_bot_template.services.utils import http_client

# Google Gen AI SDK (Vertex AI backend)
from google import genai
from google.genai import types
from google.genai.types import Modality

# Service account credentials
from google.oauth2.service_account import Credentials

logger = structlog.get_logger(__name__)


class GoogleGeminiClientResponse(BaseModel):
    """Standardized response from Gemini client."""
    image_bytes: bytes
    content_type: str = "image/png"
    response_payload: dict

    class Config:
        arbitrary_types_allowed = True


def _serialize_response(resp: Any) -> dict:
    """Safe, small logging payload; redacts inline image bytes."""
    if not resp:
        return {}
    out: dict[str, Any] = {"candidates": []}
    try:
        to_dict = getattr(resp, "to_dict", None)
        if callable(to_dict):
            d = to_dict()
        else:
            d = {}
            cand_list = getattr(resp, "candidates", None) or []
            for c in cand_list:
                # google-genai response objects also expose dict-like structure
                cdict = getattr(c, "to_dict", lambda: {"content": {}})()
                out_parts = []
                for p in cdict.get("content", {}).get("parts", []):
                    if "inline_data" in p:
                        data = p["inline_data"].get("data", b"")
                        p = {
                            "inline_data": {
                                "mime_type": p["inline_data"].get("mime_type", "image/png"),
                                "data": f"<redacted {len(data)} bytes>",
                            }
                        }
                    out_parts.append(p)
                cdict.setdefault("content", {})["parts"] = out_parts
                d.setdefault("candidates", []).append(cdict)
        return d or out
    except Exception as e:
        logger.warning("serialize_response_fallback", error=str(e))
        return {"content": str(resp)}


async def _fetch_images_as_parts(urls: Iterable[str]) -> List[types.Part]:
    """Download images and convert to google.genai.types.Part (inline bytes)."""
    results: List[types.Part] = []
    if not urls:
        return results

    session = await http_client.session()

    async def fetch(url: str) -> types.Part:
        async with session.get(url, timeout=60) as resp:
            resp.raise_for_status()
            data = await resp.read()
            mime = resp.headers.get("Content-Type", "image/png")
            # SDK accepts inline bytes; it will wrap into a UserContent internally
            return types.Part.from_bytes(data=data, mime_type=mime)

    return await asyncio.gather(*(fetch(u) for u in urls))


def _pick_best_inline_image(parts: List[Any]) -> tuple[bytes, str] | None:
    """Return the largest inline image (bytes, mime) from parts."""
    best: tuple[int, bytes, str] | None = None
    for p in parts or []:
        inline = getattr(p, "inline_data", None)
        if inline and getattr(inline, "data", None):
            data: bytes = inline.data
            mime = getattr(inline, "mime_type", None) or "image/png"
            size = len(data)
            if best is None or size > best[0]:
                best = (size, data, mime)
    if best:
        _, data, mime = best
        return data, mime
    return None


class _ImagesNamespace:
    """
    Handles image generation via Gemini API on Vertex AI using google-genai.

    Notes:
      - Uses model 'gemini-2.5-flash-image' (preview модели снимаются 31 Oct 2025).
      - Асинхронный вызов через client.aio.models.generate_content.
    """
    DEFAULT_MODEL = "gemini-2.5-flash-image"

    def __init__(self) -> None:
        # Expect: settings.google.project_id / location / service_account_creds_json
        if not all([
            getattr(settings, "google", None),
            settings.google.project_id,
            settings.google.location,
            settings.google.service_account_creds_json,
        ]):
            raise RuntimeError(
                "Missing Google Cloud configuration. "
                "Set GOOGLE__PROJECT_ID, GOOGLE__LOCATION, GOOGLE__SERVICE_ACCOUNT_CREDS_JSON."
            )

        try:
            creds_info = json.loads(
                settings.google.service_account_creds_json.get_secret_value()
            )
            base_creds = Credentials.from_service_account_info(creds_info)
            scoped_creds = base_creds.with_scopes(
                ["https://www.googleapis.com/auth/cloud-platform"]
            )

            # В google-genai клиент можно передать Vertex AI параметры напрямую;
            # он поднимет Vertex endpoint и ADC/SA creds.
            self._client = genai.Client(
                vertexai=True,
                project=settings.google.project_id,
                location=settings.google.location,  # обычно 'global' для image модели
                credentials=scoped_creds,
            )
            logger.info("GenAI client initialized (Vertex AI backend).")
        except Exception:
            logger.exception("Failed to initialize Google Gen AI client.")
            raise

    async def generate(
        self,
        status_callback: Callable[[str], Awaitable[None]] | None = None,
        **kwargs: Any,
    ) -> GoogleGeminiClientResponse:
        """Generate an image with Gemini 2.5 Flash Image."""
        model_name: str = kwargs.pop("model", self.DEFAULT_MODEL)
        prompt = kwargs.pop("prompt", "")
        image_urls = kwargs.pop("image_urls", [])
        temperature = kwargs.pop("temperature", 0.6)
        aspect_ratio = kwargs.pop("aspect_ratio", "9:16")
        top_p = kwargs.pop("top_p", 0.95)
        top_k = kwargs.pop("top_k", 32)
        max_output_tokens = kwargs.pop("max_output_tokens", 8192)
        candidate_count = kwargs.pop("candidate_count", 1)

        log = logger.bind(model=model_name)

        if status_callback:
            await status_callback("Preparing your request for Gemini...")

        parts: List[Any] = []
        # order doesn't matter; SDK группирует Parts в один UserContent
        if prompt:
            parts.append(prompt)

        if image_urls:
            image_parts = await _fetch_images_as_parts(image_urls)
            parts.extend(image_parts)

        gen_config = types.GenerateContentConfig(
            temperature=temperature,
            top_p=top_p,
            top_k=top_k,
            max_output_tokens=max_output_tokens,
            candidate_count=candidate_count,
            response_modalities=[Modality.TEXT, Modality.IMAGE],
            image_config=types.ImageConfig(
                aspect_ratio=aspect_ratio,
            ),
        )

        log.info("Calling Gemini for image generation.")
        if status_callback:
            await status_callback("Calling the Gemini API...")

        try:
            # Асинхронный вариант google-genai (эквивалент клиенту .models.generate_content)
            response = await self._client.aio.models.generate_content(
                model=model_name,
                contents=parts,
                config=gen_config,
            )
        except Exception as e:
            log.error("Gemini API error during image generation", error=e)
            raise

        if not response or not getattr(response, "candidates", None):
            log.error("Empty or invalid response from Gemini.", payload=str(response))
            raise ValueError("Gemini returned an empty or invalid response.")

        candidate = response.candidates[0]
        content = getattr(candidate, "content", None)
        parts = getattr(content, "parts", None) or []
        picked = _pick_best_inline_image(parts)

        if not picked:
            finish_reason = getattr(candidate, "finish_reason", "UNKNOWN")
            part_kinds = [
                "inline_data" if getattr(p, "inline_data", None)
                else "text" if getattr(p, "text", None)
                else "other"
                for p in parts
            ]
            log.error(
                "No inline image in response.",
                reason=finish_reason,
                part_kinds=part_kinds,
                payload=_serialize_response(response),
            )
            raise ValueError(f"No inline_data image in response. Finish reason: {finish_reason}")

        image_bytes, content_type = picked

        # Optional local smoke-check (disabled by default)
        # PILImage.open(BytesIO(image_bytes)).save("gemini_image.png")

        return GoogleGeminiClientResponse(
            image_bytes=image_bytes,
            content_type=content_type or "image/png",
            response_payload=_serialize_response(response),
        )


class GoogleGeminiClient:
    """Gemini client focused on image generation."""
    def __init__(self, **_kwargs: Any) -> None:
        self.images = _ImagesNamespace()

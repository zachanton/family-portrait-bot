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

# Vertex AI (generative) SDK
import vertexai
from vertexai.generative_models import (
    GenerativeModel,
    GenerationConfig,
    Image,  # vertexai.generative_models.Image
)
from google.genai import types


# Service account credentials
from google.oauth2.service_account import Credentials

logger = structlog.get_logger(__name__)


class GoogleGeminiClientResponse(BaseModel):
    """Standardized response from Vertex AI Gemini client."""
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
        # Most objects in vertexai responses have .to_dict()
        to_dict = getattr(resp, "to_dict", None)
        if callable(to_dict):
            d = to_dict()
        else:
            d = {}
            cand_list = getattr(resp, "candidates", None) or []
            for c in cand_list:
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


async def _fetch_images_as_vertex_inputs(urls: Iterable[str]) -> List[Image]:
    """Download images and convert to vertexai.generative_models.Image objects."""
    results: List[Image] = []
    if not urls:
        return results
    session = await http_client.session()

    async def fetch(url: str) -> Image:
        async with session.get(url, timeout=60) as resp:
            resp.raise_for_status()
            data = await resp.read()
            return Image.from_bytes(data)

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
    """Handles image generation via Vertex AI Gemini."""
    DEFAULT_MODEL = "gemini-2.5-flash-image-preview"

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
            creds = Credentials.from_service_account_info(
                creds_info,
                scopes=["https://www.googleapis.com/auth/cloud-platform"],
            )

            # Important: use vertexai.init (not aiplatform.init); location should be 'global'
            vertexai.init(
                project=settings.google.project_id,
                location=settings.google.location,  # e.g. "global" for image-preview models
                credentials=creds,
            )
            logger.info("VertexAI initialized for generative models.")
        except Exception:
            logger.exception("Failed to initialize Vertex AI client.")
            raise

    async def generate(
        self,
        status_callback: Callable[[str], Awaitable[None]] | None = None,
        **kwargs: Any,
    ) -> GoogleGeminiClientResponse:
        """Generate an image with Gemini 2.5 Flash Image Preview."""
        model_name: str = kwargs.pop("model", self.DEFAULT_MODEL)
        prompt = kwargs.pop("prompt", "")
        image_urls = kwargs.pop("image_urls", [])
        temperature = kwargs.pop("temperature", 0.6)
        aspect_ratio = kwargs.pop("aspect_ratio", "9:16")
        top_p = kwargs.pop("top_p", 0.95)
        top_k = kwargs.pop("top_k", 32)
        max_output_tokens = kwargs.pop("max_output_tokens", 8192)
        candidate_count = kwargs.pop("candidate_count", 1)

        model = GenerativeModel(model_name)
        log = logger.bind(model=model_name)

        if status_callback:
            await status_callback("Preparing your request for Vertex AI...")

        contents: List[Any] = []
        if image_urls:
            images = await _fetch_images_as_vertex_inputs(image_urls)
            contents.extend(images)
        if prompt:
            contents.append(prompt)

        # Critical: request both TEXT and IMAGE modalities for image generation.
        gen_config = GenerationConfig(
            temperature=temperature,
            top_p=top_p,
            top_k=top_k,
            max_output_tokens=max_output_tokens,
            candidate_count=candidate_count,
            response_modalities=[
                GenerationConfig.Modality.TEXT,
                GenerationConfig.Modality.IMAGE,
            ],
            image_config=types.ImageConfig(
                aspect_ratio=aspect_ratio,
            )
        )

        log.info("Calling Vertex AI Gemini for image generation.")
        if status_callback:
            await status_callback("Calling the Gemini API...")

        try:
            response = await model.generate_content_async(
                contents=contents,
                generation_config=gen_config,
            )
        except Exception as e:
            log.error("Vertex AI API error during image generation", error=e)
            raise

        if not response or not getattr(response, "candidates", None):
            log.error("Empty or invalid response from Vertex AI.", payload=str(response))
            raise ValueError("Vertex AI returned an empty or invalid response.")

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
        # PILImage.open(BytesIO(image_bytes)).save("gemini_preview.png")

        return GoogleGeminiClientResponse(
            image_bytes=image_bytes,
            content_type=content_type or "image/png",
            response_payload=_serialize_response(response),
        )


class GoogleGeminiClient:
    """Vertex AI client focused on image generation."""
    def __init__(self, **_kwargs: Any) -> None:
        self.images = _ImagesNamespace()
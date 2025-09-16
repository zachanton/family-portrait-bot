# aiogram_bot_template/services/clients/google_ai_client.py
from __future__ import annotations
import asyncio
from typing import Any, Iterable, List
from collections.abc import Awaitable, Callable

import structlog
from pydantic import BaseModel
# PIL is not used directly here; keep import if other parts rely on it.
from PIL import Image  # noqa: F401

from aiogram_bot_template.data.settings import settings
from aiogram_bot_template.services.utils import http_client

# Official Google Gen AI SDK
from google import genai
from google.genai import types, errors as genai_errors

logger = structlog.get_logger(__name__)


class GoogleGeminiClientResponse(BaseModel):
    """
    Standardized response from the Google Gemini client.
    """
    image_bytes: bytes
    content_type: str = "image/png"
    response_payload: dict

    class Config:
        arbitrary_types_allowed = True


def _redact_inline_data_in_dict(obj: Any) -> Any:
    """
    Recursively redact huge binary inline_data in dicts produced by SDK .to_dict(),
    replacing `inline_data.data` with a short descriptor to keep logs small.
    """
    if isinstance(obj, dict):
        new_obj = {}
        for k, v in obj.items():
            if k == "inline_data" and isinstance(v, dict):
                data = v.get("data")
                mime = v.get("mime_type") or v.get("mimeType")
                size_desc = f"<{len(data)} bytes>" if isinstance(data, (bytes, bytearray)) else "<redacted>"
                new_obj[k] = {"mime_type": mime, "data": size_desc}
            else:
                new_obj[k] = _redact_inline_data_in_dict(v)
        return new_obj
    if isinstance(obj, list):
        return [_redact_inline_data_in_dict(x) for x in obj]
    return obj


def _serialize_response(response: types.GenerateContentResponse) -> dict:
    """
    Safely serializes the GenerateContentResponse object to a dict for logging.
    Robust against missing/None attributes and avoids dumping megabytes of base64.
    """
    if not response:
        return {}

    try:
        out: dict[str, Any] = {}

        # candidates
        candidates_data = []
        for cand in getattr(response, "candidates", []) or []:
            cand_dict: dict[str, Any] = {}
            fr = getattr(cand, "finish_reason", None)
            cand_dict["finish_reason"] = getattr(fr, "name", "UNKNOWN")
            # ratings
            ratings = getattr(cand, "safety_ratings", None) or []
            cand_dict["safety_ratings"] = [
                r.to_dict() for r in ratings if hasattr(r, "to_dict")
            ]
            # content (redacted)
            content = getattr(cand, "content", None)
            if content and hasattr(content, "to_dict"):
                cdict = content.to_dict()
                cand_dict["content"] = _redact_inline_data_in_dict(cdict)
            candidates_data.append(cand_dict)

        out["candidates"] = candidates_data

        # prompt feedback
        feedback = getattr(response, "prompt_feedback", None)
        if feedback:
            ratings = getattr(feedback, "safety_ratings", None) or []
            out["prompt_feedback"] = {
                "safety_ratings": [r.to_dict() for r in ratings if hasattr(r, "to_dict")]
            }

        return out
    except Exception as e:
        logger.warning(
            "Could not fully serialize Gemini response, falling back to string.",
            error=str(e),
        )
        return {"error": "Could not serialize response", "content": str(response)}


async def _fetch_images_as_parts(urls: Iterable[str]) -> List[types.Part]:
    """
    Downloads images from URLs and converts them into Gemini API Part objects.
    This uses types.Part.from_bytes as per official SDK examples.
    """
    results: List[types.Part] = []
    if not urls:
        return results

    session = await http_client.session()

    async def fetch(url: str) -> types.Part:
        async with session.get(url, timeout=60) as resp:
            resp.raise_for_status()
            mime = resp.headers.get("Content-Type", "").split(";")[0].strip() or "image/png"
            data = await resp.read()
            return types.Part.from_bytes(data=data, mime_type=mime)

    return await asyncio.gather(*(fetch(u) for u in urls))


def _model_supports_image_output(model_name: str) -> bool:
    """
    Heuristic: Gemini 2.5 'image' variants (including *-image-preview) support interleaved IMAGE output.
    """
    lower = (model_name or "").lower()
    return "-image" in lower  # covers "-image" and "-image-preview"


def _pick_best_inline_image(parts: List[Any]) -> tuple[bytes, str] | None:
    """
    Scan all parts and return the largest inline image (by byte length).
    Returns (bytes, content_type) or None.
    """
    best: tuple[int, bytes, str] | None = None
    for p in parts or []:
        inline = getattr(p, "inline_data", None)
        if inline and getattr(inline, "data", None):
            data: bytes = inline.data
            mime = getattr(inline, "mime_type", None) or "image/png"
            size = len(data) if isinstance(data, (bytes, bytearray)) else 0
            if best is None or size > best[0]:
                best = (size, data, mime)
    if best:
        _, data, mime = best
        return data, mime
    return None


class _ImagesNamespace:
    """
    Handles direct image generation via the Gemini API.
    Public behavior preserved: .generate(...) returns GoogleGeminiClientResponse or raises.
    """
    DEFAULT_MODEL = "gemini-1.5-flash-latest"  # keep legacy default to avoid breaking callers

    def __init__(self) -> None:
        api_key = settings.api_urls.google_api_key
        if not api_key:
            raise RuntimeError(
                "Missing API key for Google Gemini. Set API_URLS__GOOGLE_API_KEY."
            )
        self._client = genai.Client(api_key=api_key.get_secret_value())
        logger.info("GoogleGeminiClient initialized for image generation.")

    async def generate(
        self,
        status_callback: Callable[[str], Awaitable[None]] | None = None,
        **kwargs: Any,
    ) -> GoogleGeminiClientResponse:
        """
        Generates an image using the Google Gemini API.

        Kwargs respected (non-breaking):
          - model: str
          - prompt: str
          - image_urls: list[str]
          - temperature, top_p, top_k, max_output_tokens, candidate_count
          - response_modalities: list[str] or None (will be forced to include ["TEXT","IMAGE"] if missing)
        """
        model = kwargs.pop("model", self.DEFAULT_MODEL)
        prompt = kwargs.pop("prompt", "")
        image_urls = kwargs.pop("image_urls", [])

        if status_callback:
            await status_callback("Preparing your request for Gemini...")

        contents: List[Any] = []
        if image_urls:
            parts = await _fetch_images_as_parts(image_urls)
            contents.extend(parts)
        if prompt:
            contents.append(prompt)

        # Ensure we request IMAGE output per current docs.
        # If caller passed response_modalities, extend/normalize; otherwise enforce ["TEXT","IMAGE"].
        rm = kwargs.pop("response_modalities", None)
        if not rm:
            response_modalities = ["IMAGE"]
        else:
            # normalize and ensure IMAGE is included
            response_modalities = [str(x).upper() for x in rm]
            if "IMAGE" not in response_modalities:
                response_modalities.append("IMAGE")

        gen_config = types.GenerateContentConfig(
            temperature=kwargs.pop("temperature", 0.6),
            top_p=kwargs.pop("top_p", 0.95),
            top_k=kwargs.pop("top_k", 32),
            max_output_tokens=kwargs.pop("max_output_tokens", None),
            candidate_count=kwargs.pop("candidate_count", 1),
            response_modalities=response_modalities,  # critical for image output
        )

        log = logger.bind(model=model, response_modalities=response_modalities)
        if not _model_supports_image_output(model):
            log.warning(
                "Selected model might not support image output. Consider a '*-image' variant like 'gemini-2.5-flash-image-preview'."
            )

        log.info("Sending request to Gemini API for image generation.")
        if status_callback:
            await status_callback("Calling the Gemini API...")

        try:
            response = await self._client.aio.models.generate_content(
                model=model,
                contents=contents,
                config=gen_config,
            )
        except genai_errors.APIError as e:
            log.error("Gemini API error occurred during image generation", error=e)
            raise

        try:
            if not response or not getattr(response, "candidates", None):
                log.error(
                    "Gemini returned an empty or invalid response object.",
                    payload=str(response),
                )
                raise ValueError("Gemini returned an empty or invalid response.")

            candidate = response.candidates[0]

            # Defensive checks
            content = getattr(candidate, "content", None)
            if not content or not getattr(content, "parts", None):
                finish_reason = (
                    candidate.finish_reason.name
                    if getattr(candidate, "finish_reason", None)
                    else "UNKNOWN"
                )
                log.error(
                    "Gemini response candidate has no content.",
                    reason=finish_reason,
                    payload=_serialize_response(response),
                )
                raise ValueError(
                    f"Gemini response candidate was empty. Finish reason: {finish_reason}"
                )

            parts = content.parts
            picked = _pick_best_inline_image(parts)

            if not picked:
                # Gather diagnostics for easier debugging.
                finish_reason = (
                    candidate.finish_reason.name
                    if getattr(candidate, "finish_reason", None)
                    else "UNKNOWN"
                )
                part_kinds = [
                    "inline_data" if getattr(p, "inline_data", None) else
                    "file_data" if getattr(p, "file_data", None) else
                    "text" if getattr(p, "text", None) else
                    "other"
                    for p in parts
                ]
                log.error(
                    "Gemini response did not contain an inline image.",
                    reason=finish_reason,
                    part_kinds=part_kinds,
                    payload=_serialize_response(response),
                )
                raise ValueError(f"No inline_data image in response. Finish reason: {finish_reason}")

            image_bytes, content_type = picked

            return GoogleGeminiClientResponse(
                image_bytes=image_bytes,
                content_type=content_type or "image/png",
                response_payload=_serialize_response(response),
            )
        except (IndexError, KeyError, ValueError) as e:
            log.error(
                "Failed to parse image from Gemini response",
                error=str(e),
                payload=_serialize_response(response),
            )
            raise ValueError("Could not parse a valid image from the Gemini API response.") from e


class GoogleGeminiClient:
    """A client for Google's Gemini API, focusing on image generation."""
    def __init__(self, **_kwargs: Any) -> None:
        self.images = _ImagesNamespace()

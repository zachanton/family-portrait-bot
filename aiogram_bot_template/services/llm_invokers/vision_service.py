# File: aiogram_bot_template/services/llm_invokers/vision_service.py
import json
import asyncio
import time
from typing import Any
import base64

import aiohttp
import structlog
from aiogram_bot_template.data.enums import AiFeature
from aiogram_bot_template.dto.facial_features import ImageDescription
from aiogram_bot_template.services.clients import factory as ai_client_factory
# --- NEW IMPORT ---
from aiogram_bot_template.services.google_sheets_logger import GoogleSheetsLogger

logger = structlog.get_logger(__name__)


class VisionService:
    """
    A dedicated service for analyzing facial features from an image by sending its bytes
    directly to the vision model, avoiding URL fetching issues.
    """
    _PROMPT_TEXT = (
        "You are a forensic facial analyst. Analyze the person in the photo and "
        "return ONE valid JSON object that strictly conforms to the provided JSON Schema. "
        "Output ONLY the JSON with no extra text or markdown. "
        "Describe the person's primary facial features and any worn accessories (like glasses or hats). "
        "Avoid returning null/unknown unless the attribute truly cannot be inferred from the image. "
        "If uncertain, make the best evidence-based estimate from visible cues. "
        "Boolean fields must be true or false."
    )
    _NULL_RATIO_THRESHOLD = 0.20

    def __init__(self) -> None:
        feature_config = ai_client_factory.get_feature_config(AiFeature.VISION_ANALYSIS)

        self.vision_client, self.vision_model = ai_client_factory.get_ai_client_and_model(
            feature=AiFeature.VISION_ANALYSIS
        )
        self.fallback_model = feature_config.fallback_model

    @staticmethod
    def _count_nulls(obj: Any) -> tuple[int, int]:
        """
        Recursively counts total values and null-like values in a JSON-like object.
        Null-like = None or case-insensitive strings in {"unknown","n/a","na","null"}.
        """
        def is_null_like(x: Any) -> bool:
            if x is None:
                return True
            if isinstance(x, str) and x.strip().lower() in {"unknown", "n/a", "na", "null"}:
                return True
            return False

        if isinstance(obj, dict):
            total, nulls = 0, 0
            for v in obj.values():
                t, n = VisionService._count_nulls(v)
                total += t
                nulls += n
            return total, nulls
        if isinstance(obj, list):
            total, nulls = 0, 0
            for v in obj:
                t, n = VisionService._count_nulls(v)
                total += t
                nulls += n
            return total, nulls
        return (1, 1) if is_null_like(obj) else (1, 0)

    @staticmethod
    def _null_ratio(obj: Any) -> float:
        """Calculates the ratio of null-like values to total values."""
        total, nulls = VisionService._count_nulls(obj)
        return (nulls / total) if total else 0.0

    async def _call_model(self, model_name: str, messages: list, schema: dict) -> dict[str, Any]:
        """
        Calls the VLM with strict JSON Schema and returns a parsed dict.
        Handles network retries internally.
        """
        log = logger.bind(model=model_name)
        max_retries = 3
        backoff_base = 1.5

        for attempt in range(1, max_retries + 1):
            try:
                started = time.monotonic()
                log.info("Attempting vision analysis request", attempt=attempt, messages=[m["content"][0] for m in messages])  # Log only text part
                response = await self.vision_client.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    max_tokens=768,
                    temperature=0,
                    seed=42,
                    response_format={
                        "type": "json_schema",
                        "json_schema": {
                            "name": "image_description", "schema": schema, "strict": True
                        },
                    },
                )
                duration_ms = int((time.monotonic() - started) * 1000)
                raw_content = response.choices[0].message.content
                log.info("Received vision analysis response", duration_ms=duration_ms, response=raw_content)
                return json.loads(raw_content)
            except (asyncio.TimeoutError, aiohttp.ClientError) as e:
                if attempt < max_retries:
                    await asyncio.sleep(backoff_base * attempt)
                    continue
                log.exception("Vision LLM call failed after maximum retries.", error=e)
                raise
        raise RuntimeError("Exhausted all retries for VLM call.")

    # --- UPDATED METHOD SIGNATURE ---
    async def analyze_face(
        self, image_bytes: bytes, content_type: str, image_unique_id: str | None = None
    ) -> ImageDescription | None:
        """
        Analyzes a face from image bytes, returning a structured ImageDescription.
        Uses a primary model and falls back to a stronger one if the result is sparse.
        """
        log = logger.bind()

        base64_image = base64.b64encode(image_bytes).decode("utf-8")
        data_url = f"data:{content_type};base64,{base64_image}"

        messages = [
            {"role": "user", "content": [
                {"type": "text", "text": self._PROMPT_TEXT},
                {"type": "image_url", "image_url": {"url": data_url}},
            ]}
        ]
        schema = ImageDescription.model_json_schema()

        try:
            primary_data = await self._call_model(self.vision_model, messages, schema)
            
            # --- ADDED LOGGING CALL ---
            if image_unique_id:
                asyncio.create_task(
                    GoogleSheetsLogger().log_vision_analysis(
                        image_unique_id=image_unique_id,
                        model_name=self.vision_model,
                        result_data=primary_data,
                    )
                )

            primary_ratio = self._null_ratio(primary_data)
            log.info("Primary model null ratio computed", null_ratio=primary_ratio, model=self.vision_model)

            if primary_ratio > self._NULL_RATIO_THRESHOLD and self.fallback_model:
                log.warning(
                    "High null ratio detected, retrying with fallback model.",
                    null_ratio=primary_ratio, fallback_model=self.fallback_model
                )
                fallback_data = await self._call_model(self.fallback_model, messages, schema)

                # --- ADDED LOGGING CALL FOR FALLBACK ---
                if image_unique_id:
                    asyncio.create_task(
                        GoogleSheetsLogger().log_vision_analysis(
                            image_unique_id=image_unique_id,
                            model_name=self.fallback_model,
                            result_data=fallback_data,
                        )
                    )
                return ImageDescription.model_validate(fallback_data)

            return ImageDescription.model_validate(primary_data)

        except json.JSONDecodeError as e:
            log.error("Received malformed JSON despite strict schema.", error=str(e))
            return None
        except Exception:
            log.exception("An unexpected error occurred during the face analysis pipeline.")
            return None
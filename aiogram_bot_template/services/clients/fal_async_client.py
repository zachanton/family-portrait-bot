# File: aiogram_bot_template/services/clients/fal_async_client.py
from __future__ import annotations

import asyncio
import json
import math
import os
from contextlib import suppress
from typing import Any
from collections.abc import Awaitable, Callable

import aiohttp
import structlog

from aiogram_bot_template.data.settings import settings
from aiogram_bot_template.services.utils import http_client

logger = structlog.get_logger(__name__)

FAL_QUEUE_BASE = "https://queue.fal.run"
DEFAULT_REQUEST_TIMEOUT_S = 300
POLL_INTERVAL_S = 0.8
POLL_INTERVAL_MAX_S = 4.0
MAX_HTTP_RETRIES = 3


class FalJobError(Exception):
    pass


class FalAsyncClient:
    """
    Agnostic, async, non-blocking client for the fal.ai Queue API.
    """

    def __init__(self, concurrency_limit: int = 8) -> None:
        secret = settings.api_urls.fal_api_key.get_secret_value() if settings.api_urls.fal_api_key else None
        self._api_key = os.getenv("FAL_KEY") or secret
        if not self._api_key:
            raise RuntimeError("FAL_KEY is missing. Set env var or settings.api_urls.fal_api_key.")
        self._sem = asyncio.Semaphore(concurrency_limit)
        logger.info("FalAsyncClient initialized", concurrency=concurrency_limit)

    async def generate(
        self,
        model_id: str,
        arguments: dict[str, Any],
        *,
        request_timeout_s: int = DEFAULT_REQUEST_TIMEOUT_S,
        status_callback: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
    ) -> dict[str, Any]:
        """
        Submits a request to the fal queue and polls for the result.
        Returns a dict with keys: "response", "image_bytes", "content_type".
        """
        async with self._sem:
            headers = {"Authorization": f"Key {self._api_key}", "Content-Type": "application/json"}
            submit_url = self._build_submit_url(model_id)

            submit_resp = await self._retry_request("POST", submit_url, headers=headers, json_data=arguments)

            request_id = submit_resp.get("request_id")
            status_url = submit_resp.get("status_url")
            response_url = submit_resp.get("response_url")
            cancel_url = submit_resp.get("cancel_url")

            if not (request_id and status_url and response_url and cancel_url):
                raise FalJobError(f"Invalid submit response: {submit_resp}")

            logger.info("fal.submit.ok", request_id=request_id, model_id=model_id)

            try:
                return await asyncio.wait_for(
                    self._poll_until_ready(
                        status_url=status_url,
                        response_url=response_url,
                        headers=headers,
                        status_callback=status_callback,
                    ),
                    timeout=request_timeout_s,
                )
            except asyncio.TimeoutError:
                try:
                    await self._retry_request("POST", cancel_url, headers=headers)
                    logger.warning("fal.job.cancelled", request_id=request_id)
                except Exception:
                    logger.exception("fal.job.cancel.failed", request_id=request_id)
                raise FalJobError(f"fal job timed out (request_id={request_id})")

    def _build_submit_url(self, model_id: str) -> str:
        return f"{FAL_QUEUE_BASE}/{model_id}"

    async def _poll_until_ready(self, *, status_url: str, response_url: str, headers: dict[str, str], status_callback: Callable | None) -> dict[str, Any]:
        attempt = 0
        interval = POLL_INTERVAL_S

        while True:
            status = await self._retry_request("GET", f"{status_url}?logs=1", headers=headers)
            state = status.get("status")

            if status_callback:
                with suppress(Exception):
                    await status_callback(status)

            logger.debug("fal.status", state=state, queue_pos=status.get("queue_position"))

            if state in {"COMPLETED", "SUCCEEDED"}:
                response = await self._retry_request("GET", response_url, headers=headers)
                image_bytes, content_type = await self._download_result_image(response)
                return {"response": response, "image_bytes": image_bytes, "content_type": content_type}

            if state in {"FAILED", "CANCELLED", "ERROR"}:
                raise FalJobError(f"fal job ended with state={state}: {status}")

            await asyncio.sleep(interval)
            attempt += 1
            interval = min(POLL_INTERVAL_MAX_S, POLL_INTERVAL_S * math.pow(1.3, attempt))

    async def _download_result_image(self, response: dict[str, Any]) -> tuple[bytes | None, str | None]:
        image_url = self._extract_first_image_url(response)
        if not image_url:
            return None, None

        data, ctype = await self._retry_request("GET", image_url, headers={}, response_type="bytes")
        return data, ctype

    async def _retry_request(self, method: str, url: str, headers: dict, json_data: dict | None = None, response_type: str = "json") -> Any:
        session = await http_client.session()
        for i in range(MAX_HTTP_RETRIES + 1):
            try:
                async with session.request(method, url, headers=headers, json=json_data) as resp:
                    resp.raise_for_status()

                    if response_type == "bytes":
                        return await resp.read(), resp.headers.get("Content-Type")

                    text = await resp.text()
                    return json.loads(text) if text else {}
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                if i >= MAX_HTTP_RETRIES:
                    logger.error("HTTP request failed after all retries", method=method, url=url, error=str(e))
                    raise
                await asyncio.sleep(0.3 * (2 ** i))
        raise AssertionError("Unreachable")

    def _extract_first_image_url(self, response: dict[str, Any]) -> str | None:
        if images := response.get("images"):
            if isinstance(images, list) and images and isinstance(images[0], dict):
                return images[0].get("url")
        if image := response.get("image"):
            if isinstance(image, dict):
                return image.get("url")
        return None

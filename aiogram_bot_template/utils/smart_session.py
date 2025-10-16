# aiogram_bot_template/utils/smart_session.py
import asyncio
import time
from typing import Any

import structlog.typing
from aiogram import Bot, types
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.exceptions import (
    RestartingTelegram,
    TelegramRetryAfter,
    TelegramServerError,
    TelegramBadRequest,
)
from aiogram.methods.base import TelegramMethod, TelegramType

from aiogram_bot_template.data.settings import settings


class StructLogAiogramAiohttpSessions(AiohttpSession):
    def __init__(
        self,
        logger: structlog.typing.FilteringBoundLogger,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._logger = logger

    async def make_request(
        self,
        bot: Bot,
        method: TelegramMethod[TelegramType],
        timeout: int | None = None,
    ) -> TelegramType:
        req_logger = self._logger.bind(
            bot=bot.token.split(":")[0],  # Log only bot ID for security
            method=method.model_dump(exclude_none=True, exclude_unset=True),
            timeout=timeout,
            api=self.api,
            url=self.api.api_url(bot.token, method.__api_method__),
        )
        st = time.monotonic()
        req_logger.debug("Making request to API")
        try:
            res = await super().make_request(bot, method, timeout)
        except TelegramBadRequest as e:
            # Check for specific, non-critical errors and log them as warnings.
            if "message to delete not found" in str(e).lower() or "message is not modified" in str(e).lower():
                req_logger.warning(
                    "API warning (non-critical)",
                    error=str(e),
                    time_spent_ms=(time.monotonic() - st) * 1000,
                )
            else:
                # Log other BadRequest errors as exceptions.
                req_logger.exception(
                    "API error: TelegramBadRequest",
                    error=e,
                    time_spent_ms=(time.monotonic() - st) * 1000,
                )
            raise
        except Exception as e:
            req_logger.exception(
                "API error",
                error=e,
                time_spent_ms=(time.monotonic() - st) * 1000,
            )
            raise
        req_logger.debug(
            "API response",
            response=(
                res.model_dump(exclude_none=True, exclude_unset=True)
                if hasattr(res, "model_dump")
                else res
            ),
            time_spent_ms=(time.monotonic() - st) * 1000,
        )
        return res


class SmartAiogramAiohttpSession(StructLogAiogramAiohttpSessions):
    MAX_RETRY_THRESHOLD: int = 6

    async def make_request(
        self,
        bot: Bot,
        method: TelegramMethod[TelegramType],
        timeout: int | None = None,
    ) -> TelegramType:
        attempt = 0
        while True:
            attempt += 1
            try:
                response = await super().make_request(bot, method, timeout)
            except TelegramRetryAfter as e:
                await asyncio.sleep(e.retry_after)
            except (RestartingTelegram, TelegramServerError):
                sleepy_time = 2**attempt
                if attempt > self.MAX_RETRY_THRESHOLD:
                    sleepy_time = 64
                await asyncio.sleep(sleepy_time)
            except Exception:
                raise
            else:
                return response

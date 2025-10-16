# aiogram_bot_template/utils/status_manager.py
import asyncio
import time
from contextlib import suppress

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest


class StatusMessageManager:
    """
    Manages a single status message, ensuring each update is visible for a minimum duration.
    """

    def __init__(
        self,
        bot: Bot,
        chat_id: int,
        message_id: int,
        min_duration: float = 1.5,
    ) -> None:
        self.bot = bot
        self.chat_id = chat_id
        self.message_id = message_id
        self.min_duration = min_duration
        self._last_update_time = time.monotonic()

    async def _wait_if_needed(self) -> None:
        """Waits for the remainder of the minimum duration if necessary."""
        elapsed = time.monotonic() - self._last_update_time
        if elapsed < self.min_duration:
            await asyncio.sleep(self.min_duration - elapsed)

    async def update(self, text: str) -> None:
        """
        Updates the status message text, waiting if the previous message was shown too briefly.
        """
        await self._wait_if_needed()
        with suppress(TelegramBadRequest):
            await self.bot.edit_message_text(
                text=text,
                chat_id=self.chat_id,
                message_id=self.message_id,
            )
        self._last_update_time = time.monotonic()

    async def delete(self) -> None:
        """

        Deletes the status message, waiting if the last update was shown too briefly.
        """
        await self._wait_if_needed()
        with suppress(TelegramBadRequest):
            await self.bot.delete_message(chat_id=self.chat_id, message_id=self.message_id)

from typing import Any
from collections.abc import Awaitable, Callable

import structlog
from aiogram import BaseMiddleware, Bot
from aiogram.types import TelegramObject, Update
from aiogram_bot_template.data.settings import settings

logger = structlog.get_logger(__name__)


class DebugForwardingMiddleware(BaseMiddleware):
    def __init__(self) -> None:
        """Middleware for forwarding user interactions to a debug chat."""
        self.log_chat_id = settings.bot.log_chat_id

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if not self.log_chat_id:
            return await handler(event, data)

        if not isinstance(event, Update):
            return await handler(event, data)

        try:
            bot: Bot = data["bot"]
            user = data.get("event_from_user")

            # Check that the message exists and that it is not a service message about payment
            if event.message and not event.message.successful_payment:
                await bot.forward_message(
                    chat_id=self.log_chat_id,
                    from_chat_id=event.message.chat.id,
                    message_id=event.message.message_id,
                    disable_notification=True,
                )
            elif event.callback_query:
                if user:
                    user_info = (
                        f"@{user.username}" if user.username else f"ID: {user.id}"
                    )
                    text = (
                        f"👇 Button press by {user_info}:\n\n"
                        f"Data: `{event.callback_query.data}`"
                    )
                else:
                    text = f"👇 Button press:\n\nData: `{event.callback_query.data}`"

                await bot.send_message(
                    chat_id=self.log_chat_id,
                    text=text,
                    disable_notification=True,
                )

        except Exception:
            logger.exception(
                "Failed to forward debug message", log_chat_id=self.log_chat_id
            )

        return await handler(event, data)

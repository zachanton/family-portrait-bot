from collections.abc import Awaitable, Callable
from typing import Any, TYPE_CHECKING

from aiogram import BaseMiddleware
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.types import TelegramObject
from aiogram.utils.i18n import I18n

from aiogram_bot_template.db.db_api.storages import PostgresConnection
from aiogram_bot_template.db.repo.users import get_user_language

if TYPE_CHECKING:
    import asyncpg


class I18nMiddleware(BaseMiddleware):
    def __init__(self, i18n: I18n) -> None:
        self.i18n = i18n

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        locale = self.i18n.default_locale
        user_locale = None
        redis_key = f"user_lang:{user.id}" if user else None

        if user:
            storage: RedisStorage | None = data.get("storage")
            if isinstance(storage, RedisStorage) and redis_key:
                cached_lang_bytes = await storage.redis.get(redis_key)
                if cached_lang_bytes:
                    user_locale = cached_lang_bytes.decode("utf-8")

            if not user_locale:
                db_pool: asyncpg.Pool | None = data.get("db_pool")
                if db_pool:
                    db = PostgresConnection(db_pool, logger=data["business_logger"])
                    db_lang = await get_user_language(db, user.id)
                    if db_lang:
                        user_locale = db_lang

            if (
                not user_locale
                and user.language_code
                and user.language_code in self.i18n.available_locales
            ):
                user_locale = user.language_code

            if user_locale:
                locale = user_locale

        if isinstance(storage, RedisStorage) and redis_key:
            await storage.redis.set(redis_key, locale, ex=86400)

        data["locale"] = locale
        with self.i18n.context(), self.i18n.use_locale(locale):
            return await handler(event, data)

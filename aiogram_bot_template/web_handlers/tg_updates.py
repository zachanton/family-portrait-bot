import secrets
from typing import Any, TYPE_CHECKING

import orjson
from aiogram import Bot, Dispatcher, types
from aiohttp import web

from aiogram_bot_template.data.settings import settings

if TYPE_CHECKING:
    import aiojobs

# We will just define the handler and register it in bot.py


async def process_update(
    upd: types.Update,
    bot: Bot,
    dp: Dispatcher,
    workflow_data: dict[str, Any],
) -> None:
    await dp.feed_webhook_update(bot, upd, **workflow_data)


async def tg_webhook_handler(req: web.Request) -> web.Response:
    secret_token = settings.webhook.secret_token.get_secret_value()
    if not secrets.compare_digest(
        req.headers.get("X-Telegram-Bot-Api-Secret-Token", ""), secret_token
    ):
        raise web.HTTPNotFound

    if req.match_info["bot_id"] != str(settings.bot.id):
        raise web.HTTPNotFound

    dp: Dispatcher = req.app["dp"]
    scheduler: aiojobs.Scheduler = req.app["scheduler"]

    if scheduler.pending_count > settings.bot.max_updates_in_queue:
        raise web.HTTPTooManyRequests
    if scheduler.closed:
        raise web.HTTPServiceUnavailable(reason="Closed queue")

    workflow_data = {"app": req.app, "dp": dp, "scheduler": scheduler}

    await scheduler.spawn(
        process_update(
            types.Update(**(await req.json(loads=orjson.loads))),
            req.app["bot"],
            dp,
            workflow_data,
        ),
    )

    return web.Response()

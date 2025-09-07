# aiogram_bot_template/bot.py
import asyncio
import sys
from typing import TYPE_CHECKING
from urllib.parse import urlparse

import aiojobs
import orjson
import tenacity
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.telegram import TelegramAPIServer
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.utils.i18n import I18n
from aiohttp import web
from redis.asyncio import Redis

from aiogram_bot_template import utils
from aiogram_bot_template.data import config_helpers
from aiogram_bot_template.data.settings import settings
from aiogram_bot_template.middlewares.i18n import I18nMiddleware
from aiogram_bot_template.middlewares import StructLoggingMiddleware
from aiogram_bot_template.middlewares.debug_forwarding import DebugForwardingMiddleware
from aiogram_bot_template.web_handlers.file_cache_server import (
    routes as file_cache_routes,
)
from aiogram_bot_template.web_handlers.tg_updates import tg_webhook_handler

from aiogram_bot_template.handlers import (
    error,
    menu,
    payment_handler,
    utility,
    photo_handler,
    options_handler,
    prompt_handler,
    quality_handler,
    next_step_handler,
    settings as settings_handler,
    feedback_handler,
)
from aiogram_bot_template.services.clients import local_ai_client

if TYPE_CHECKING:
    import asyncpg
    import structlog


async def setup_aiohttp_app(bot: Bot, dp: Dispatcher) -> web.Application:  # noqa: RUF029
    scheduler = aiojobs.Scheduler()
    app = web.Application()

    # Parse the URL from settings to guarantee a path starting with "/"
    webhook_url_from_settings = str(settings.webhook.address)
    webhook_path_from_url = urlparse(webhook_url_from_settings).path

    # Assemble the full path for the handler
    full_webhook_path = f"{webhook_path_from_url.rstrip('/')}/bot/{{bot_id}}"

    app.router.add_post(full_webhook_path, tg_webhook_handler)

    app["bot"] = bot
    app["dp"] = dp
    app["scheduler"] = scheduler
    app.on_startup.append(aiohttp_on_startup)
    app.on_shutdown.append(aiohttp_on_shutdown)
    return app


async def create_db_connections(dp: Dispatcher) -> None:
    logger: structlog.typing.FilteringBoundLogger = dp["business_logger"]
    try:
        db_pool = await utils.connect_to_services.wait_postgres(
            logger=dp["db_logger"], dsn=settings.db.pg_link
        )
        dp["db_pool"] = db_pool
    except tenacity.RetryError:
        logger.exception("Failed to connect to PostgreSQL")
        sys.exit(1)

    try:
        redis_pool = await utils.connect_to_services.wait_redis_pool(
            logger=dp["cache_logger"],
            host=settings.redis.host,
            port=settings.redis.port,
            username=settings.redis.username,
            password=settings.redis.password.get_secret_value()
            if settings.redis.password
            else None,
            database=settings.redis.cache_db,
        )
        dp["cache_pool"] = redis_pool
    except tenacity.RetryError:
        logger.exception("Failed to connect to Redis")
        sys.exit(1)


async def close_db_connections(dp: Dispatcher) -> None:
    if "db_pool" in dp.workflow_data:
        db_pool: asyncpg.Pool = dp["db_pool"]
        await db_pool.close()
    if "cache_pool" in dp.workflow_data:
        cache_pool: Redis = dp["cache_pool"]
        await cache_pool.aclose()


def setup_handlers(dp: Dispatcher) -> None:
    # Global error handler should be first
    dp.include_router(error.router)

    # Routers with global commands that should work in any state
    dp.include_router(menu.router)         # Handles /start, /menu
    dp.include_router(settings_handler.router)  # Handles /language
    dp.include_router(utility.router)      # Handles /help, /privacy, etc.

    # Routers for the main generation FSM flow, now registered after global commands
    dp.include_router(photo_handler.router)
    dp.include_router(prompt_handler.router)
    dp.include_router(options_handler.router)
    dp.include_router(quality_handler.router)
    dp.include_router(payment_handler.router)
    dp.include_router(next_step_handler.router)
    dp.include_router(feedback_handler.router)


def setup_middlewares(dp: Dispatcher) -> None:
    dp.update.outer_middleware(DebugForwardingMiddleware())
    dp.update.outer_middleware(StructLoggingMiddleware(logger=dp["aiogram_logger"]))


def setup_logging(dp: Dispatcher) -> None:
    dp["aiogram_logger"] = utils.logging.setup_logger().bind(type="aiogram")
    dp["db_logger"] = utils.logging.setup_logger().bind(type="db")
    dp["cache_logger"] = utils.logging.setup_logger().bind(type="cache")
    dp["business_logger"] = utils.logging.setup_logger().bind(type="business")


async def setup_aiogram(dp: Dispatcher) -> None:
    logger = dp["aiogram_logger"]
    logger.debug("Configuring aiogram")
    await create_db_connections(dp)
    setup_handlers(dp)
    setup_middlewares(dp)
    logger.info("Configured aiogram")


async def aiohttp_on_startup(app: web.Application) -> None:
    dp: Dispatcher = app["dp"]
    bot: Bot = app["bot"]
    dp["aiogram_logger"].debug("Starting file proxy server")
    app["proxy_runner"] = await start_proxy_server(bot, dp)
    workflow_data = {"app": app, "dispatcher": dp, "bot": bot}
    await dp.emit_startup(**workflow_data)
    if config_helpers.is_local_generation_enabled():
        logger = dp.get("business_logger", utils.logging.setup_logger())
        logger.info("Local generation is enabled, starting warmup...")
        try:
            await local_ai_client.warmup(getattr(logger, "_logger", None))
        except Exception:  # noqa: BLE001
            dp["aiogram_logger"].warning(
                "Bento warmup failed during startup", exc_info=True
            )


async def aiohttp_on_shutdown(app: web.Application) -> None:
    dp: Dispatcher = app["dp"]
    if "proxy_runner" in app:
        dp["aiogram_logger"].debug("Stopping file proxy server")
        await app["proxy_runner"].cleanup()
        dp["aiogram_logger"].info("Stopped file proxy server")
    workflow_data = {"app": app, "dispatcher": dp, "bot": app.get("bot")}
    await dp.emit_shutdown(**workflow_data)


async def aiogram_on_startup(dispatcher: Dispatcher, bot: Bot) -> None:
    await setup_aiogram(dispatcher)

    webhook_logger = dispatcher["aiogram_logger"].bind(
        webhook_url=str(settings.webhook.address),
    )
    webhook_logger.debug("Configuring webhook")

    webhook_url_for_telegram = (
        f"{str(settings.webhook.address).rstrip('/')}/bot/{settings.bot.id}"
    )

    await bot.set_webhook(
        url=webhook_url_for_telegram,
        allowed_updates=dispatcher.resolve_used_update_types(),
        secret_token=settings.webhook.secret_token.get_secret_value(),
    )
    webhook_logger.info("Configured webhook")


async def aiogram_on_shutdown(dispatcher: Dispatcher) -> None:
    dispatcher["aiogram_logger"].debug("Stopping webhook")
    await close_db_connections(dispatcher)
    await dispatcher.storage.close()
    dispatcher["aiogram_logger"].info("Stopped webhook")


async def start_proxy_server(bot: Bot, dp: Dispatcher) -> web.AppRunner:
    proxy_app = web.Application()
    proxy_app.add_routes(file_cache_routes)
    proxy_app["bot"] = bot
    proxy_app["dp"] = dp
    runner = web.AppRunner(proxy_app)
    await runner.setup()
    site = web.TCPSite(
        runner,
        host=settings.proxy.listening_host,
        port=settings.proxy.listening_port,
    )
    await site.start()
    logger = dp.get("aiogram_logger", utils.logging.setup_logger())
    logger.info(
        "Image proxy server started",
        host=settings.proxy.listening_host,
        port=settings.proxy.listening_port,
    )
    return runner


def main() -> None:
    aiogram_session_logger = utils.logging.setup_logger().bind(type="aiogram_session")

    api_server = TelegramAPIServer.from_base("https://api.telegram.org")
    if settings.use_custom_api_server and settings.custom_api_server:
        api_server = TelegramAPIServer(
            base=settings.custom_api_server.base,
            file=settings.custom_api_server.file,
        )

    session = utils.smart_session.SmartAiogramAiohttpSession(
        api=api_server,
        json_loads=orjson.loads,
        logger=aiogram_session_logger,
    )

    bot = Bot(
        token=settings.bot.token.get_secret_value(),
        session=session,
        default=DefaultBotProperties(parse_mode="HTML"),
    )

    fsm_redis = Redis(
        host=settings.redis.host,
        port=settings.redis.port,
        db=settings.redis.fsm_db,
        username=settings.redis.username,
        password=settings.redis.password.get_secret_value()
        if settings.redis.password
        else None,
    )
    storage = RedisStorage(redis=fsm_redis)

    dp = Dispatcher(storage=storage)
    dp["storage"] = storage

    i18n = I18n(
        path="aiogram_bot_template/locales", default_locale="en", domain="messages"
    )
    dp.update.outer_middleware(I18nMiddleware(i18n))
    dp["i18n"] = i18n

    setup_logging(dp)
    dp["aiogram_session_logger"] = aiogram_session_logger

    dp.startup.register(aiogram_on_startup)
    dp.shutdown.register(aiogram_on_shutdown)

    web.run_app(
        asyncio.run(setup_aiohttp_app(bot, dp)),
        handle_signals=True,
        host=settings.webhook.listening_host,
        port=settings.webhook.listening_port,
    )


if __name__ == "__main__":
    main()

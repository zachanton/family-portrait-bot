# aiogram_bot_template/handlers/payment_handler.py
import json
import asyncpg
import structlog
import aiojobs
from redis.asyncio import Redis
from aiogram import Bot, Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, PreCheckoutQuery, LabeledPrice
from aiogram.filters import StateFilter
from aiogram.utils.i18n import gettext as _, ngettext
from contextlib import suppress
from aiogram.exceptions import TelegramBadRequest

from aiogram_bot_template.data.constants import GenerationType
from aiogram_bot_template.data.settings import settings
from aiogram_bot_template.db.db_api.storages import PostgresConnection
from aiogram_bot_template.db.repo import (
    generations as generations_repo,
    payments as payments_repo,
)
from aiogram_bot_template.services import generation_worker
from aiogram_bot_template.states.user import Generation
from aiogram_bot_template.services.photo_processing_manager import PhotoProcessingManager


router = Router(name="payment-handler")


async def send_stars_invoice(
    msg: Message,
    request_id: int,
    generation_type: GenerationType,
    description: str,
    *,
    quality: int,
) -> Message | None:
    """
    Sends a Telegram Stars invoice, dynamically getting the price based on the generation type.
    """
    try:
        generation_config = getattr(settings, generation_type.value)
        tier_config = generation_config.tiers.get(quality)
    except (AttributeError, KeyError):
        tier_config = None
    
    if not tier_config or not isinstance(tier_config.price, int) or tier_config.price <= 0:
        await msg.answer(_("Could not determine the price. Please try again."))
        structlog.get_logger(__name__).error(
            "Invalid price configuration for invoice", quality=quality, gen_type=generation_type.value
        )
        return None

    label = ngettext(
        "🎨 {count} Portrait",
        "🎨 {count} Portraits",
        tier_config.count
    ).format(count=tier_config.count)

    payload = json.dumps({"req_id": request_id})

    sent_message = await msg.bot.send_invoice(
        chat_id=msg.chat.id,
        title=_("🖼️ Portrait Generation"),
        description=description,
        payload=payload,
        currency="XTR",
        prices=[LabeledPrice(label=label, amount=tier_config.price)],
    )
    return sent_message


@router.pre_checkout_query()
async def pre_checkout(pre_checkout_query: PreCheckoutQuery, bot: Bot) -> None:
    """
    This handler MUST answer every pre-checkout query within 10 seconds.
    It confirms to Telegram that the bot is ready to process the payment.
    """
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)


@router.message(F.successful_payment, StateFilter(Generation.waiting_for_payment))
async def successful_payment(
    message: Message,
    state: FSMContext,
    db_pool: asyncpg.Pool,
    cache_pool: Redis,
    business_logger: structlog.typing.FilteringBoundLogger,
    bot: Bot,
    scheduler: aiojobs.Scheduler,
    photo_manager: PhotoProcessingManager,
) -> None:
    """
    Handles a successful payment, logs it, and spawns the generation worker.
    """
    payment_info = message.successful_payment

    try:
        payload = json.loads(payment_info.invoice_payload)
        request_id = int(payload["req_id"])
    except (json.JSONDecodeError, KeyError, ValueError, TypeError):
        await message.answer(_("There was an issue processing your payment data. Please contact support."))
        business_logger.error("Failed to parse payment payload", payload=payment_info.invoice_payload)
        return

    user_data = await state.get_data()
    db = PostgresConnection(db_pool, logger=business_logger)

    request_details = await generations_repo.get_request_details_with_sources(db, request_id)
    if not request_details or request_details.get("status") != "awaiting_payment":
        log = business_logger.bind(request_id=request_id)
        log.warning(
            "Received payment for an invalid or already processed request.",
            status=request_details.get("status") if request_details else "not_found",
        )
        await state.clear()
        return

    await payments_repo.log_successful_payment(db, message.from_user.id, request_id, payment_info)
    await generations_repo.update_generation_request_status(db, request_id, "paid")

    status_message_id = user_data.get("status_message_id")
    if status_message_id:
        with suppress(TelegramBadRequest):
            await bot.edit_message_text(
                text=_("✅ Payment received! Starting generation..."),
                chat_id=message.chat.id,
                message_id=status_message_id
            )
    else:
        status_msg = await message.answer(_("✅ Payment received! Starting generation..."))
        status_message_id = status_msg.message_id
        business_logger.warning("Could not find status_message_id in state to edit, sent a new one.")

    await scheduler.spawn(
        generation_worker.run_generation_worker(
            bot=bot,
            chat_id=message.chat.id,
            status_message_id=status_message_id,
            db_pool=db_pool,
            cache_pool=cache_pool,
            business_logger=business_logger,
            state=state,
            photo_manager=photo_manager,
        )
    )
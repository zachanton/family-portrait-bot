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
from aiogram.utils.i18n import gettext as _
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

router = Router(name="payment-handler")

from aiogram_bot_template.keyboards.inline.quality import _get_translated_quality_name



async def send_stars_invoice(
    msg: Message,
    request_id: int,
    generation_type: GenerationType,
    *,
    quality: int | None = None,
) -> Message | None:
    price = -1
    label = "Standard"
    tier_config = None

    generation_config = getattr(settings, generation_type.value, None)
    if generation_config and quality is not None:
        tier_config = generation_config.tiers.get(quality)

    if tier_config:
        price = tier_config.price
        label = _get_translated_quality_name(quality)

    if not isinstance(price, int) or price <= 0:
        error_text = _("Could not determine the price for this service. The operation has been cancelled.")
        await msg.answer(error_text)
        business_logger = structlog.get_logger(__name__).bind(request_id=request_id)
        business_logger.error(
            "Invoice price validation failed",
            price=price,
            gen_type=generation_type.value,
            quality=quality,
        )
        return None

    payload = json.dumps({"req_id": request_id})
    sent_message = await msg.bot.send_invoice(
        chat_id=msg.chat.id,
        title=_("🎨 {label} Image Generation").format(label=label),
        description=_("Please confirm your payment, and I'll start creating your unique portrait right away!"),
        payload=payload,
        currency="XTR",
        prices=[LabeledPrice(label=_("⭐ {label} Quality").format(label=label), amount=price)],
        start_parameter="pay",
        reply_markup=None,
    )
    return sent_message


@router.pre_checkout_query(StateFilter(Generation.waiting_for_payment))
async def pre_checkout(pre_checkout_query: PreCheckoutQuery, bot: Bot) -> None:
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
) -> None:
    payment_info = message.successful_payment
    try:
        payload = json.loads(payment_info.invoice_payload)
        request_id = int(payload["req_id"])
    except (json.JSONDecodeError, KeyError, ValueError, TypeError):
        await message.answer(_("There was an issue processing your payment data. Please contact support."))
        business_logger.error("Failed to parse payload", payload=payment_info.invoice_payload)
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
        await message.answer(
            _("This payment is for an outdated or cancelled request. It has been ignored. Please start a new generation with /start.")
        )
        await state.clear()
        return

    await payments_repo.log_successful_payment(db, message.from_user.id, request_id, payment_info)
    await generations_repo.update_generation_request_status(db, request_id, "paid")
    business_logger.info("Payment successful, status updated to 'paid'", request_id=request_id)
    await state.update_data(request_id=request_id)

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
        business_logger.warning("Could not find status_message_id in state to edit.")

    await scheduler.spawn(
        generation_worker.run_generation_worker(
            bot=bot,
            user_id=message.from_user.id,
            chat_id=message.chat.id,
            status_message_id=status_message_id,
            db_pool=db_pool,
            cache_pool=cache_pool,
            business_logger=business_logger,
            state=state,
        )
    )

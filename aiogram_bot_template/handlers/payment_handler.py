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
    quality: int,
) -> Message | None:
    tier_config = settings.group_photo.tiers.get(quality)
    if not tier_config or tier_config.price <= 0:
        await msg.answer(_("Could not determine the price. Please try again."))
        return None

    label = _get_translated_quality_name(quality)
    payload = json.dumps({"req_id": request_id})
    sent_message = await msg.bot.send_invoice(
        chat_id=msg.chat.id,
        title=_("🎨 Group Portrait Generation"),
        description=_("Confirm payment to create your unique group portrait!"),
        payload=payload,
        currency="XTR",
        prices=[LabeledPrice(label=_("⭐ {label} Quality").format(label=label), amount=tier_config.price)],
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
    payload = json.loads(payment_info.invoice_payload)
    request_id = int(payload["req_id"])

    user_data = await state.get_data()
    db = PostgresConnection(db_pool, logger=business_logger)

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
    
    await scheduler.spawn(
        generation_worker.run_generation_worker(
            bot=bot,
            chat_id=message.chat.id,
            status_message_id=status_message_id,
            db_pool=db_pool,
            cache_pool=cache_pool,
            business_logger=business_logger,
            state=state,
        )
    )
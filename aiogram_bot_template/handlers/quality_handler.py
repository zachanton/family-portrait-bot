# aiogram_bot_template/handlers/quality_handler.py
import asyncpg
import structlog
import aiojobs
from redis.asyncio import Redis
from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from aiogram.filters import StateFilter
from aiogram.utils.i18n import gettext as _
from contextlib import suppress
from aiogram.exceptions import TelegramBadRequest

from aiogram_bot_template.data.constants import GenerationType
from aiogram_bot_template.db.db_api.storages import PostgresConnection
from aiogram_bot_template.db.repo import generations as generations_repo, users as users_repo
from aiogram_bot_template.handlers import payment_handler
from aiogram_bot_template.states.user import Generation
from aiogram_bot_template.data.settings import settings
from aiogram_bot_template.services import generation_worker
from aiogram_bot_template.keyboards.inline.quality import quality_kb # Добавим импорт для возврата клавиатуры

router = Router(name="quality-handler")

@router.callback_query(
    StateFilter(Generation.waiting_for_quality), F.data.startswith("quality:")
)
async def process_quality_selection(
    cb: CallbackQuery,
    state: FSMContext,
    db_pool: asyncpg.Pool,
    cache_pool: Redis,
    business_logger: structlog.typing.FilteringBoundLogger,
    bot: Bot,
    scheduler: aiojobs.Scheduler,
) -> None:
    await cb.answer()
    user_data = await state.get_data()
    db = PostgresConnection(db_pool, logger=business_logger)
    request_id = user_data.get("request_id")
    user_id = cb.from_user.id

    try:
        quality_val = int(cb.data.split(":", 1)[1])
        await state.update_data(quality=quality_val)
    except (ValueError, IndexError):
        await cb.message.answer(_("An error occurred. Please start over with /cancel."))
        return

    with suppress(TelegramBadRequest):
        await cb.message.delete()

    await generations_repo.update_generation_request_status(db, request_id, "quality_selected")
    
    is_in_whitelist = user_id in settings.free_trial_whitelist

    if quality_val == 0:
        has_used_trial = await users_repo.get_user_trial_status(db, user_id)
        
        # --- ИЗМЕНЕНИЕ: Отклоняем, только если юзер НЕ в вайтлисте И уже использовал попытку ---
        if not is_in_whitelist and has_used_trial:
            await cb.message.answer(
                _("Your free trial has already been used. Please choose a paid quality level to proceed:"),
                reply_markup=quality_kb(is_trial_available=False)
            )
            return

        status_msg = await cb.message.answer(
            _("✅ Thank you! Preparing your free request..."), reply_markup=None
        )
        
        # --- ИЗМЕНЕНИЕ: Правильно определяем тип бесплатной попытки для аналитики ---
        trial_type_to_log = "whitelist" if is_in_whitelist else "free_trial"
        await state.update_data(trial_type=trial_type_to_log)
        
        # Помечаем попытку использованной, только если юзер НЕ в вайтлисте
        if not is_in_whitelist:
            await users_repo.mark_free_trial_as_used(db, user_id)

        await scheduler.spawn(
            generation_worker.run_generation_worker(
                bot=bot,
                chat_id=cb.message.chat.id,
                status_message_id=status_msg.message_id,
                db_pool=db_pool,
                cache_pool=cache_pool,
                business_logger=business_logger,
                state=state,
            )
        )
        return
    
    # Логика для платных тиров остается прежней
    status_msg = await cb.message.answer(_("✅ Got it! Preparing your payment..."))
    
    tier_config = settings.group_photo.tiers.get(quality_val)
    if not tier_config or tier_config.price <= 0:
        await status_msg.edit_text(_("A price configuration error occurred. Please try again later."))
        return

    await generations_repo.update_generation_request_status(db, request_id, "awaiting_payment")
    invoice_message = await payment_handler.send_stars_invoice(
        msg=cb.message, request_id=request_id, generation_type=GenerationType.GROUP_PHOTO, quality=quality_val
    )
    if invoice_message:
        await state.update_data(invoice_message_id=invoice_message.message_id, status_message_id=status_msg.message_id)
    await state.set_state(Generation.waiting_for_payment)
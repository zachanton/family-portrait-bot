# aiogram_bot_template/handlers/quality_handler.py
import asyncpg
import structlog
import aiojobs
from redis.asyncio import Redis
from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from aiogram.filters import StateFilter
from aiogram.utils.i18n import gettext as _, ngettext
from contextlib import suppress
from aiogram.exceptions import TelegramBadRequest

from aiogram_bot_template.data.constants import GenerationType
from aiogram_bot_template.db.db_api.storages import PostgresConnection
from aiogram_bot_template.db.repo import generations as generations_repo, users as users_repo
from aiogram_bot_template.handlers import payment_handler
from aiogram_bot_template.states.user import Generation
from aiogram_bot_template.data.settings import settings
from aiogram_bot_template.services import generation_worker
from aiogram_bot_template.keyboards.inline.quality import quality_kb
# --- NEW IMPORTS ---
from aiogram_bot_template.keyboards.inline.style_selection import style_selection_kb
from aiogram_bot_template.keyboards.inline.callbacks import StyleCallback


router = Router(name="quality-handler")


async def _proceed_to_payment_or_worker(
    cb: CallbackQuery,
    state: FSMContext,
    db_pool: asyncpg.Pool,
    cache_pool: Redis,
    business_logger: structlog.typing.FilteringBoundLogger,
    bot: Bot,
    scheduler: aiojobs.Scheduler,
) -> None:
    """
    Shared logic to either start the generation worker (for free tiers)
    or initiate the payment flow (for paid tiers).
    This is called after all parameters, including style, have been selected.
    """
    user_data = await state.get_data()
    db = PostgresConnection(db_pool, logger=business_logger)
    request_id = user_data.get("request_id")
    user_id = cb.from_user.id
    quality_val = user_data.get("quality_level")
    generation_type_str = user_data.get("generation_type")
    generation_type = GenerationType(generation_type_str)
    
    generation_config = getattr(settings, generation_type.value)
    tier_config = generation_config.tiers.get(quality_val)

    with suppress(TelegramBadRequest):
        await cb.message.delete()

    await generations_repo.update_generation_request_status(db, request_id, "quality_selected")
    
    is_in_whitelist = user_id in settings.free_trial_whitelist

    # Logic for the free tier
    if quality_val == 0:
        has_used_trial = await users_repo.get_user_trial_status(db, cb.from_user.id)
        
        if not (user_id in settings.free_trial_whitelist) and has_used_trial:
            await cb.message.answer(
                _("Your free trial has already been used. Please choose a paid package to proceed:"),
                reply_markup=quality_kb(
                    generation_type=generation_type, 
                    is_trial_available=False
                )
            )
            return

        status_msg = await cb.message.answer(
            _("✅ Thank you! Preparing your free portrait..."), reply_markup=None
        )
        
        trial_type_to_log = "whitelist" if is_in_whitelist else "free_trial"
        await state.update_data(trial_type=trial_type_to_log)
        
        if not is_in_whitelist:
            await users_repo.mark_free_trial_as_used(db, user_id)

        await scheduler.spawn(
            generation_worker.run_generation_worker(
                bot=bot, chat_id=cb.message.chat.id, status_message_id=status_msg.message_id,
                db_pool=db_pool, cache_pool=cache_pool, business_logger=business_logger, state=state,
            )
        )
        return
    
    # Logic for paid tiers
    description = ngettext(
        "Confirm payment to create your unique portrait!",
        "Confirm payment to create your {count} unique portraits!",
        tier_config.count
    ).format(count=tier_config.count)

    status_msg = await cb.message.answer(_("✅ Got it! Preparing your payment..."))
    
    if tier_config.price <= 0:
        await status_msg.edit_text(_("A price configuration error occurred. Please try again later."))
        return

    await generations_repo.update_generation_request_status(db, request_id, "awaiting_payment")
    invoice_message = await payment_handler.send_stars_invoice(
        msg=cb.message, request_id=request_id, generation_type=generation_type, 
        quality=quality_val, description=description
    )
    if invoice_message:
        await state.update_data(invoice_message_id=invoice_message.message_id, status_message_id=status_msg.message_id)
    await state.set_state(Generation.waiting_for_payment)


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

    try:
        quality_val = int(cb.data.split(":", 1)[1])
        await state.update_data(quality_level=quality_val)
    except (ValueError, IndexError):
        await cb.message.answer(_("An error occurred. Please start over with /cancel."))
        return

    generation_type_str = user_data.get("generation_type")
    if not generation_type_str:
        await cb.message.answer(_("A critical error occurred (type missing). Please start over with /cancel."))
        return
    generation_type = GenerationType(generation_type_str)

    if generation_type == GenerationType.PAIR_PHOTO:
        await state.set_state(Generation.choosing_pair_photo_style)
        with suppress(TelegramBadRequest):
            await cb.message.edit_text(
                _("Great! Now, select a style for your couple portrait:"),
                reply_markup=style_selection_kb()
            )
    else:
        # For all other generation types, proceed as before
        await _proceed_to_payment_or_worker(
            cb, state, db_pool, cache_pool, business_logger, bot, scheduler
        )


@router.callback_query(
    StyleCallback.filter(), StateFilter(Generation.choosing_pair_photo_style)
)
async def process_style_selection(
    cb: CallbackQuery,
    callback_data: StyleCallback,
    state: FSMContext,
    db_pool: asyncpg.Pool,
    cache_pool: Redis,
    business_logger: structlog.typing.FilteringBoundLogger,
    bot: Bot,
    scheduler: aiojobs.Scheduler,
):
    """Handles the selection of a pair photo style and then proceeds to payment/worker."""
    await cb.answer()
    await state.update_data(pair_photo_style=callback_data.style_id)

    # Now that the style is selected, we can proceed with the standard flow
    await _proceed_to_payment_or_worker(
        cb, state, db_pool, cache_pool, business_logger, bot, scheduler
    )
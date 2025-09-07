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

from aiogram_bot_template.data.settings import settings
from aiogram_bot_template.data.constants import GenerationType
from aiogram_bot_template.db.db_api.storages import PostgresConnection
from aiogram_bot_template.db.repo import generations as generations_repo, users as users_repo
from aiogram_bot_template.handlers import payment_handler
from aiogram_bot_template.services import generation_worker
from aiogram_bot_template.states.user import Generation
from aiogram_bot_template.dto.generation_parameters import GenerationParameters
from aiogram_bot_template.keyboards.inline import trial_confirm, generation_quality, quality, next_step

router = Router(name="quality-handler")


async def _deactivate_previous_photo_message(
    bot: Bot,
    chat_id: int,
    user_data: dict,
    log: structlog.typing.FilteringBoundLogger
) -> None:
    """Finds and deactivates the previous photo message by editing its keyboard."""
    photo_msg_id = user_data.get("active_photo_message_id")
    gen_id = user_data.get("active_generation_id")

    if photo_msg_id and gen_id:
        log.info("Deactivating previous photo message", msg_id=photo_msg_id, gen_id=gen_id)
        with suppress(TelegramBadRequest):
            await bot.edit_message_reply_markup(
                chat_id=chat_id,
                message_id=photo_msg_id,
                reply_markup=next_step.get_return_to_generation_kb(gen_id)
            )

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
    """
    Handles user's quality selection.
    If quality '0' (free) is chosen, it verifies eligibility and asks for marketing consent.
    For other qualities, it proceeds to payment.
    """
    await cb.answer()
    user_data = await state.get_data()
    db = PostgresConnection(db_pool, logger=business_logger, decode_json=True)
    user_id = cb.from_user.id

    try:
        quality_val = int(cb.data.split(":", 1)[1])
        await state.update_data(quality=quality_val)
    except (ValueError, IndexError):
        await cb.message.answer(_("A critical error occurred. Please start over with /cancel."))
        return

    request_id = user_data.get("request_id")
    if not request_id:
        await cb.message.answer(_("A critical error occurred. Please start over with /cancel."))
        return

    # Deactivate the previous control message, as we are now proceeding.
    with suppress(TelegramBadRequest):
        await cb.message.delete()

    await generations_repo.update_generation_request_status(db, request_id, "quality_selected")

    generation_type = GenerationType(user_data.get("generation_type"))

    if quality_val == 0:
        is_in_whitelist = user_id in settings.free_trial_whitelist
        has_used_trial = await users_repo.get_user_trial_status(db, user_id)

        if not is_in_whitelist and has_used_trial:
            await cb.answer(_("Your free trial has already been used. Please select a paid option."), show_alert=True)
            return

        consent_text = _(
            "✨ <b>You get one FREE creation!</b> ✨\n\n"
            "To help me grow as an AI artist and show others my magic, I'd love your permission to respectfully use "
            "the photos you provided and the generated portrait in promotional materials (like posts on social media or our website).\n\n"
            "Your privacy is important: all images will be used anonymously, and your personal data will never be shared.\n\n"
            "<b>Do you agree to these terms for your free trial?</b>"
        )
        await cb.message.answer(consent_text, reply_markup=trial_confirm.trial_confirm_kb())
        await state.set_state(Generation.waiting_for_trial_confirm)
        return

    await _deactivate_previous_photo_message(bot, cb.message.chat.id, user_data, business_logger)
    status_msg = await cb.message.answer(_("✅ Got it! Preparing your request..."))

    price = -1
    generation_config = getattr(settings, generation_type.value, None)
    if not generation_config:
        await cb.message.answer(_("A configuration error occurred. Please try again later."))
        return

    tier_config = generation_config.tiers.get(quality_val)
    if tier_config:
        price = tier_config.price

    if price <= 0:
        await cb.message.answer(_("A price configuration error occurred. Please try again later."))
        return

    await generations_repo.update_generation_request_status(db, request_id, "awaiting_payment")
    invoice_message = await payment_handler.send_stars_invoice(
        msg=cb.message, request_id=request_id, generation_type=generation_type, quality=quality_val
    )
    if invoice_message:
        await state.update_data(invoice_message_id=invoice_message.message_id, status_message_id=status_msg.message_id)
    await state.set_state(Generation.waiting_for_payment)


@router.callback_query(
    StateFilter(Generation.waiting_for_trial_confirm), F.data.startswith("trial_confirm:")
)
async def process_trial_confirm(
    cb: CallbackQuery,
    state: FSMContext,
    db_pool: asyncpg.Pool,
    cache_pool: Redis,
    business_logger: structlog.typing.FilteringBoundLogger,
    bot: Bot,
    scheduler: aiojobs.Scheduler,
) -> None:
    await cb.answer()
    action = cb.data.split(":", 1)[1]
    user_id = cb.from_user.id
    user_data = await state.get_data()
    request_id = user_data.get("request_id")
    db = PostgresConnection(db_pool, logger=business_logger)

    if action == "yes":
        await _deactivate_previous_photo_message(bot, cb.message.chat.id, user_data, business_logger)
        
        status_msg = await cb.message.edit_text(
            _("✅ Thank you! Preparing your request..."), reply_markup=None
        )
        
        is_in_whitelist = user_id in settings.free_trial_whitelist
        trial_type_to_log = "whitelist" if is_in_whitelist else "free_trial"
        await state.update_data(trial_type=trial_type_to_log)

        if not is_in_whitelist:
            await users_repo.mark_free_trial_as_used(db, user_id)

        await scheduler.spawn(
            generation_worker.run_generation_worker(
                bot=bot, user_id=user_id, chat_id=cb.message.chat.id,
                status_message_id=status_msg.message_id, db_pool=db_pool,
                cache_pool=cache_pool, business_logger=business_logger, state=state,
            )
        )
    elif action == "no":
        gen_type = GenerationType(user_data.get("generation_type"))
        continue_key = user_data.get("continue_key")
        
        text = _("No problem. Please choose a paid quality level to proceed:")
        markup = quality.quality_kb(
            is_trial_available=True,
            continue_key=continue_key,
            request_id=request_id
        )
        if gen_type == GenerationType.UPSCALE:
            markup = quality.upscale_quality_kb(True, continue_key, request_id)
        else:
             markup = generation_quality.generation_quality_kb(True, gen_type, continue_key=continue_key, request_id=request_id)

        await cb.message.edit_text(text, reply_markup=markup)
        await state.set_state(Generation.waiting_for_quality)
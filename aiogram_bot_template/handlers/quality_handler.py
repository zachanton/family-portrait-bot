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
from aiogram_bot_template.keyboards.inline.callbacks import StyleCallback


router = Router(name="quality-handler")

async def _forward_photos_to_log_chat(
    bot: Bot,
    state: FSMContext,
    user_id: int,
    log: structlog.typing.FilteringBoundLogger
) -> None:
    """
    Forwards user-uploaded photos for the current session to the log chat.
    """
    if not settings.bot.log_chat_id:
        log.warning("BOT__LOG_CHAT_ID is not set. Cannot forward photos.")
        return

    user_data = await state.get_data()
    photos = user_data.get("photos_collected", [])
    
    if not photos:
        log.warning("No photos found in state to forward for live queue.")
        return
        
    try:
        await bot.send_message(
            settings.bot.log_chat_id,
            f"--- Live Queue Entry ---\nUser ID: `{user_id}`\nPhotos below:"
        )
        
        # Forward photos one by one
        for photo in photos:
            # Here we get the message_id that we saved in the photo_handler
            message_id = photo.get('message_id')
            if message_id:
                with suppress(TelegramBadRequest):
                    await bot.forward_message(
                        chat_id=settings.bot.log_chat_id,
                        from_chat_id=user_id, # The user's chat is the source
                        message_id=message_id
                    )
            else:
                # This log will tell you if something is still wrong
                log.warning("Cannot forward photo, message_id is missing.", photo_info=photo)

        log.info("Successfully forwarded photos to log chat for live queue.", count=len(photos))
    except Exception:
        log.exception("Failed to forward photos to log chat.")


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
    
    # --- UPDATED: Logic for the free tier (whitelist only) ---
    if quality_val == 0:
        if user_id not in settings.free_trial_whitelist:
            await cb.message.answer(
                _("Sorry, the free trial is currently available only for selected users.")
            )
            return

        status_msg = await cb.message.answer(
            _("✅ Thank you! Preparing your free portrait..."), reply_markup=None
        )
        
        await state.update_data(trial_type="whitelist")
        
        await scheduler.spawn(
            generation_worker.run_generation_worker(
                bot=bot, chat_id=cb.message.chat.id, status_message_id=status_msg.message_id,
                db_pool=db_pool, cache_pool=cache_pool, business_logger=business_logger, state=state,
            )
        )
        return
    
    # Logic for paid tiers (q > 1)
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
    StyleCallback.filter(), StateFilter(Generation.choosing_pair_photo_style)
)
async def process_pair_style_selection(
    cb: CallbackQuery,
    callback_data: StyleCallback,
    state: FSMContext,
    db_pool: asyncpg.Pool,
    business_logger: structlog.typing.FilteringBoundLogger,
    bot: Bot,
):
    await cb.answer()
    await state.update_data(pair_photo_style=callback_data.style_id)

    user_data = await state.get_data()
    message_ids_to_delete = user_data.get("style_preview_message_ids", [])
    if message_ids_to_delete:
        for msg_id in message_ids_to_delete:
            with suppress(TelegramBadRequest):
                await bot.delete_message(chat_id=cb.message.chat.id, message_id=msg_id)

    db = PostgresConnection(db_pool, logger=business_logger)
    user_id = cb.from_user.id
    generation_type = GenerationType(user_data["generation_type"])

    is_in_whitelist = user_id in settings.free_trial_whitelist
    has_used_queue = await users_repo.get_user_live_queue_status(db, user_id)

    await state.set_state(Generation.waiting_for_quality)
    await cb.message.answer(
        _("Excellent choice! Now, please choose a generation package:"),
        reply_markup=quality_kb(
            generation_type=generation_type,
            is_trial_available=is_in_whitelist,
            is_live_queue_available=not has_used_queue
        ),
    )


@router.callback_query(
    StyleCallback.filter(), StateFilter(Generation.choosing_family_photo_style)
)
async def process_family_style_selection(
    cb: CallbackQuery,
    callback_data: StyleCallback,
    state: FSMContext,
    db_pool: asyncpg.Pool,
    business_logger: structlog.typing.FilteringBoundLogger,
    bot: Bot,
):
    await cb.answer()
    await state.update_data(family_photo_style=callback_data.style_id)

    user_data = await state.get_data()
    message_ids_to_delete = user_data.get("style_preview_message_ids", [])
    if message_ids_to_delete:
        for msg_id in message_ids_to_delete:
            with suppress(TelegramBadRequest):
                await bot.delete_message(chat_id=cb.message.chat.id, message_id=msg_id)

    db = PostgresConnection(db_pool, logger=business_logger)
    user_id = cb.from_user.id
    generation_type = GenerationType(user_data["generation_type"])

    is_in_whitelist = user_id in settings.free_trial_whitelist
    has_used_queue = await users_repo.get_user_live_queue_status(db, user_id)

    await state.set_state(Generation.waiting_for_quality)
    await cb.message.answer(
        _("Style selected! Finally, please choose a generation package:"),
        reply_markup=quality_kb(
            generation_type=generation_type,
            is_trial_available=is_in_whitelist,
            is_live_queue_available=not has_used_queue
        ),
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
    Handles the final quality selection for ANY generation type, including the new Live Queue.
    """
    await cb.answer()

    try:
        quality_val = int(cb.data.split(":", 1)[1])
        await state.update_data(quality_level=quality_val)
    except (ValueError, IndexError):
        await cb.message.answer(_("An error occurred. Please start over with /cancel."))
        return
    
    # --- NEW: Logic for Tier 1 (Live Queue) ---
    if quality_val == 1:
        db = PostgresConnection(db_pool, logger=business_logger)
        user_id = cb.from_user.id
        
        has_used_queue = await users_repo.get_user_live_queue_status(db, user_id)
        if has_used_queue:
            with suppress(TelegramBadRequest):
                await cb.message.edit_text(
                    _("You have already used your free spot in the live queue. Please choose another option.")
                )
            return

        await users_repo.mark_live_queue_as_used(db, user_id)
        
        await _forward_photos_to_log_chat(bot, state, user_id, business_logger)

        channel_url = settings.bot.live_queue_channel_url
        final_text = (
            _("✅ Success! You've been added to the live queue.\n\n"
              "Keep an eye on our channel for your result: {channel_url}").format(channel_url=channel_url)
            if channel_url
            else _("You have been successfully added to the queue! Your result will be posted soon.")
        )
        
        with suppress(TelegramBadRequest):
            await cb.message.edit_text(final_text)
        
        await state.clear()
        return
    
    # For all other tiers (0 and >1), proceed to the worker or payment
    await _proceed_to_payment_or_worker(
        cb, state, db_pool, cache_pool, business_logger, bot, scheduler
    )
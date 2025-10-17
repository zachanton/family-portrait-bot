# aiogram_bot_template/handlers/quality_handler.py
import asyncpg
import structlog
import aiojobs
import asyncio
from redis.asyncio import Redis
from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, BufferedInputFile, InputMediaPhoto
from aiogram.filters import StateFilter
from aiogram.utils.i18n import gettext as _, ngettext
from contextlib import suppress
from aiogram.exceptions import TelegramBadRequest
from typing import Set

from aiogram_bot_template.data.constants import GenerationType, ImageRole, ChildAge
from aiogram_bot_template.db.db_api.storages import PostgresConnection
from aiogram_bot_template.db.repo import generations as generations_repo, users as users_repo
from aiogram_bot_template.handlers import payment_handler
from aiogram_bot_template.states.user import Generation
from aiogram_bot_template.data.settings import settings
from aiogram_bot_template.services import generation_worker, image_cache
from aiogram_bot_template.keyboards.inline.quality import quality_kb
from aiogram_bot_template.keyboards.inline.callbacks import StyleCallback
from aiogram_bot_template.keyboards.inline import session_actions as session_actions_kb
from aiogram_bot_template.services.photo_processing_manager import PhotoProcessingManager
from aiogram_bot_template.services.pipelines.pair_photo_pipeline import styles as pair_styles
from aiogram_bot_template.services.pipelines.family_photo_pipeline import styles as family_styles


router = Router(name="quality-handler")

async def _forward_collages_to_log_chat(
    bot: Bot,
    state: FSMContext,
    cache_pool: Redis,
    user_id: int,
    log: structlog.typing.FilteringBoundLogger
) -> None:
    """
    Sends the generated parent collages and session parameters as a single
    media group message to the log chat.
    """
    if not settings.bot.log_chat_id:
        log.warning("BOT__LOG_CHAT_ID is not set. Cannot forward collages.")
        return

    user_data = await state.get_data()
    mom_collage_uid = user_data.get(f"{ImageRole.MOTHER.value}_collage_uid")
    dad_collage_uid = user_data.get(f"{ImageRole.FATHER.value}_collage_uid")
    
    if not mom_collage_uid or not dad_collage_uid:
        log.warning("No collage UIDs found in state to forward for live queue.")
        return
        
    try:
        # 1. Fetch collage bytes
        (mom_bytes, _), (dad_bytes, _) = await asyncio.gather(
            image_cache.get_cached_image_bytes(mom_collage_uid, cache_pool),
            image_cache.get_cached_image_bytes(dad_collage_uid, cache_pool)
        )

        if not mom_bytes or not dad_bytes:
            log.error("Failed to retrieve one or both collage bytes from cache.")
            return

        # 2. Build the detailed caption
        caption_lines = [
            f"<b>--- Live Queue Entry ---</b>\n",
            f"👤 <b>User ID:</b> <code>{user_id}</code>"
        ]
        
        gen_type_str = user_data.get("generation_type")
        if gen_type_str == GenerationType.CHILD_GENERATION.value:
            caption_lines.append("\n🚀 <b>Pipeline:</b> Child Generation\n")
            caption_lines.append("<b>📋 Parameters:</b>")
            
            gender = user_data.get('child_gender', 'N/A').capitalize()
            resemblance = user_data.get('child_resemblance', 'N/A').capitalize()
            age_val = user_data.get('child_age')
            
            age_map = {
                ChildAge.INFANT.value: "Baby (1-3 years)",
                ChildAge.CHILD.value: "Child (5-6 years)",
                ChildAge.PRETEEN.value: "Preteen (10-11 years)",
            }
            age = age_map.get(age_val, 'N/A')

            caption_lines.append(f" • <b>Gender:</b> {gender}")
            caption_lines.append(f" • <b>Age:</b> {age}")
            caption_lines.append(f" • <b>Resemblance:</b> {resemblance}")

        elif gen_type_str == GenerationType.PAIR_PHOTO.value:
            caption_lines.append("\n🚀 <b>Pipeline:</b> Couple Portrait\n")
            caption_lines.append("<b>🎨 Style:</b>")

            style_id = user_data.get('pair_photo_style', 'N/A')
            style_name = pair_styles.STYLES.get(style_id, {}).get("name", style_id)
            caption_lines.append(f" • {style_name}")

        caption = "\n".join(caption_lines)

        # 3. Create the media group
        media = [
            InputMediaPhoto(media=BufferedInputFile(mom_bytes, f"{mom_collage_uid}.jpg"), caption=caption),
            InputMediaPhoto(media=BufferedInputFile(dad_bytes, f"{dad_collage_uid}.jpg"))
        ]

        # 4. Send the media group
        await bot.send_media_group(chat_id=settings.bot.log_chat_id, media=media)

        log.info("Successfully forwarded collages and info to log chat for live queue.")
    except Exception:
        log.exception("Failed to forward collages as media group to log chat.")


async def _proceed_to_payment_or_worker(
    cb: CallbackQuery,
    state: FSMContext,
    db_pool: asyncpg.Pool,
    cache_pool: Redis,
    business_logger: structlog.typing.FilteringBoundLogger,
    bot: Bot,
    scheduler: aiojobs.Scheduler,
    photo_manager: PhotoProcessingManager,
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
        # We delete the message with the quality keyboard
        await cb.message.delete()
        # For edits, we also delete the original image message that had the prompt request
        if generation_type == GenerationType.IMAGE_EDIT:
            original_message_id = user_data.get("edit_source_message_id")
            if original_message_id:
                await bot.delete_message(chat_id=cb.message.chat.id, message_id=original_message_id)

    # For edits, the request status is 'editing', we update it. For others, 'quality_selected'.
    new_status = "quality_selected_edit" if generation_type == GenerationType.IMAGE_EDIT else "quality_selected"
    await generations_repo.update_generation_request_status(db, request_id, new_status)
    
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
                photo_manager=photo_manager
            )
        )
        return
    
    description = ngettext(
        "Confirm payment to create your unique portrait!",
        "Confirm payment to create your {count} unique portraits!",
        tier_config.count
    ).format(count=tier_config.count)
    if generation_type == GenerationType.IMAGE_EDIT:
        description = _("Confirm payment to edit your portrait.")


    status_msg = await cb.message.answer(_("✅ Got it! Preparing your payment..."))
    
    if not tier_config or tier_config.price <= 0:
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
        await state.update_data(style_preview_message_ids=[])

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
        await state.update_data(style_preview_message_ids=[])

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
    StateFilter(Generation.waiting_for_quality, Generation.waiting_for_edit_quality),  # <-- UPDATED
    F.data.startswith("quality:")
)
async def process_quality_selection(
    cb: CallbackQuery,
    state: FSMContext,
    db_pool: asyncpg.Pool,
    cache_pool: Redis,
    business_logger: structlog.typing.FilteringBoundLogger,
    bot: Bot,
    scheduler: aiojobs.Scheduler,
    photo_manager: PhotoProcessingManager,
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
    
    user_data = await state.get_data()
    generation_type = user_data.get("generation_type")

    # The Live Queue option should not be presented or processed for edits
    if quality_val == 1 and generation_type != GenerationType.IMAGE_EDIT.value:
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
        
        await _forward_collages_to_log_chat(bot, state, cache_pool, user_id, business_logger)

        with suppress(TelegramBadRequest):
            await cb.message.delete()
        
        channel_url = settings.bot.live_queue_channel_url
        success_text = (
            _("✅ Success! You've been added to the live queue.\n\n"
              "Keep an eye on our channel for your result: {channel_url}").format(channel_url=channel_url)
            if channel_url
            else _("You have been successfully added to the queue! Your result will be posted soon.")
        )
        await cb.message.answer(success_text)

        generated_in_session: Set[str] = set(user_data.get("generated_in_session", []))
        if generation_type:
            generated_in_session.add(generation_type)
        await state.update_data(generated_in_session=list(generated_in_session))
        
        next_step_text = _("\nWhat would you like to do next?")
        session_actions_msg = await cb.message.answer(
            text=next_step_text,
            reply_markup=session_actions_kb.session_actions_kb(generated_in_session)
        )

        await state.set_state(Generation.waiting_for_next_action)
        await state.update_data(next_step_message_id=session_actions_msg.message_id)
        return
    
    await _proceed_to_payment_or_worker(
        cb, state, db_pool, cache_pool, business_logger, bot, scheduler, photo_manager
    )
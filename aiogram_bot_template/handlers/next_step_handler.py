# aiogram_bot_template/handlers/next_step_handler.py
import asyncpg
import structlog
from aiogram import F, Router, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from aiogram.filters import StateFilter
from aiogram.utils.i18n import gettext as _
from contextlib import suppress
from aiogram.exceptions import TelegramBadRequest

from . import menu
from aiogram_bot_template.data.constants import GenerationType, ImageRole
from aiogram_bot_template.db.db_api.storages import PostgresConnection
from aiogram_bot_template.db.repo import generations as generations_repo, users as users_repo
from aiogram_bot_template.keyboards.inline.callbacks import (
    RetryGenerationCallback, ContinueWithImageCallback, CreateFamilyPhotoCallback
)
from aiogram_bot_template.keyboards.inline import child_selection as child_selection_kb
from aiogram_bot_template.keyboards.inline.gender import gender_kb
from aiogram_bot_template.keyboards.inline.quality import quality_kb
from aiogram_bot_template.states.user import Generation
from aiogram_bot_template.data.settings import settings
from .menu import _cleanup_selection_messages

router = Router(name="next-step-handler")


@router.callback_query(F.data == "start_new", StateFilter("*"))
async def start_new_generation(
    callback: CallbackQuery,
    state: FSMContext,
):
    """Handles 'Start New' button, cleans up previous messages before restarting."""
    await callback.answer()
    
    if not callback.message:
        await menu.send_welcome_message(callback.message, state, is_restart=True)
        return

    # This is a key cleanup point
    await _cleanup_selection_messages(callback.bot, callback.message.chat.id, state)
    
    with suppress(TelegramBadRequest):
        await callback.message.delete()
            
    await menu.send_welcome_message(callback.message, state, is_restart=True)


@router.callback_query(
    RetryGenerationCallback.filter(),
    StateFilter(Generation.waiting_for_next_action, Generation.child_selected),
)
async def process_retry_generation(
    cb: CallbackQuery,
    callback_data: RetryGenerationCallback,
    state: FSMContext,
    db_pool: asyncpg.Pool,
    business_logger: structlog.typing.FilteringBoundLogger
):
    """
    Handles the "Try again" button. This action ends the current selection session,
    so we perform a full cleanup before starting the new flow.
    """
    await cb.answer()
    if not cb.message:
        return

    # This is a key cleanup point
    await _cleanup_selection_messages(cb.bot, cb.message.chat.id, state)
    with suppress(TelegramBadRequest):
        await cb.message.delete()
    
    db = PostgresConnection(db_pool, logger=business_logger)
    original_request = await generations_repo.get_request_details_with_sources(
        db, callback_data.request_id
    )
    if not original_request or not original_request.get("source_images"):
        await cb.message.answer(
            _("Could not find the original photos. Please start over with /start.")
        )
        return

    source_images_dto = [
        (img["file_unique_id"], img["file_id"], img["role"])
        for img in original_request["source_images"]
    ]

    draft = generations_repo.GenerationRequestDraft(
        user_id=cb.from_user.id,
        status="photos_collected",
        source_images=source_images_dto,
    )
    new_request_id = await generations_repo.create_generation_request(db, draft)

    await state.set_state(Generation.choosing_child_gender)
    await state.update_data(
        request_id=new_request_id,
        photos_collected=[
            {"file_id": img[1], "file_unique_id": img[0]} for img in source_images_dto
        ],
        is_retry=True,
        generation_type=GenerationType.CHILD_GENERATION.value,
        photo_message_ids=[],
        next_step_message_id=None,
    )

    await cb.message.answer(
        _("Let's try again! Please choose the desired gender for your child:"),
        reply_markup=gender_kb(),
    )


@router.callback_query(ContinueWithImageCallback.filter(), StateFilter(Generation.waiting_for_next_action))
async def process_continue_with_image(
    cb: CallbackQuery,
    callback_data: ContinueWithImageCallback,
    state: FSMContext,
    db_pool: asyncpg.Pool,
    business_logger: structlog.typing.FilteringBoundLogger,
    bot: Bot,
):
    """
    Handles the selection of a child image.
    - Deletes the PREVIOUS "You've selected..." message if it exists.
    - Sends a NEW "You've selected..." message.
    - Keeps the buttons on the original photos intact, allowing the user to change their mind.
    """
    await cb.answer()
    
    if not cb.message:
        business_logger.warning("CallbackQuery without a message in process_continue_with_image")
        return

    user_data = await state.get_data()
    chat_id = cb.message.chat.id
    
    # Delete the previous selection message to avoid clutter
    previous_selection_message_id = user_data.get("next_step_message_id")
    if previous_selection_message_id:
        with suppress(TelegramBadRequest):
            await bot.delete_message(chat_id=chat_id, message_id=previous_selection_message_id)

    db = PostgresConnection(db_pool, logger=business_logger)
    sql = "SELECT result_file_id FROM generations WHERE id = $1"
    result = await db.fetchrow(sql, (callback_data.generation_id,))
    
    if not result or not result.data or not result.data.get("result_file_id"):
        await cb.message.answer(_("I couldn't find the selected image. Please start over using /start."))
        await state.clear()
        return

    selected_file_id = result.data["result_file_id"]

    # Send a new message with the selected photo and next actions
    sent_message = await bot.send_photo(
        chat_id=chat_id,
        photo=selected_file_id,
        caption=_("You've selected this child.\n\nWhat would you like to do next?"),
        reply_markup=child_selection_kb.post_child_selection_kb(
            generation_id=callback_data.generation_id,
            request_id=callback_data.request_id
        )
    )
    
    await state.set_state(Generation.child_selected)
    # Store the ID of this new message. It will be deleted if the user selects another child
    # or when the session is fully cleaned up.
    await state.update_data(
        next_step_message_id=sent_message.message_id
    )


@router.callback_query(CreateFamilyPhotoCallback.filter(), StateFilter(Generation.child_selected))
async def process_create_family_photo(
    cb: CallbackQuery,
    callback_data: CreateFamilyPhotoCallback,
    state: FSMContext,
    db_pool: asyncpg.Pool,
    business_logger: structlog.typing.FilteringBoundLogger,
):
    """
    Initiates the family photo generation flow. This is treated as a continuation
    of the current session, so the child selection interface is NOT cleaned up here.
    """
    await cb.answer()
    if not cb.message:
        return

    await cb.message.edit_caption(
        caption=_("Got it! Preparing the family photoshoot..."),
        reply_markup=None
    )

    db = PostgresConnection(db_pool, logger=business_logger)
    user_id = cb.from_user.id
    
    try:
        parent_request = await generations_repo.get_request_details_with_sources(db, callback_data.parent_request_id)
        if not parent_request or len(parent_request.get("source_images", [])) < 2:
            raise ValueError("Could not find original parent photos.")
            
        parent_sources = parent_request["source_images"]
        father_source = next((img for img in parent_sources if img.get('role') == ImageRole.FATHER.value), parent_sources[1])
        mother_source = next((img for img in parent_sources if img.get('role') == ImageRole.MOTHER.value), parent_sources[0])
        father_source['role'] = ImageRole.FATHER.value
        mother_source['role'] = ImageRole.MOTHER.value

        sql_child = "SELECT result_image_unique_id, result_file_id FROM generations WHERE id = $1"
        child_res = await db.fetchrow(sql_child, (callback_data.child_generation_id,))
        if not child_res.data:
            raise ValueError("Could not find the selected child's image data.")
        
        child_source = {
            "file_unique_id": child_res.data["result_image_unique_id"],
            "file_id": child_res.data["result_file_id"],
            "role": ImageRole.CHILD.value,
        }

        all_sources = [father_source, mother_source, child_source]
        source_images_dto = [(img["file_unique_id"], img["file_id"], img["role"]) for img in all_sources]

        draft = generations_repo.GenerationRequestDraft(
            user_id=user_id, status="params_collected", source_images=source_images_dto
        )
        new_request_id = await generations_repo.create_generation_request(db, draft)
        
        # <--- ИЗМЕНЕНИЕ: Мы больше не сбрасываем message IDs здесь.
        # Они остаются в состоянии до тех пор, пока не будет вызван /start или /cancel.
        await state.update_data(
            request_id=new_request_id,
            generation_type=GenerationType.FAMILY_PHOTO.value,
            photos_collected=all_sources
        )

        is_in_whitelist = user_id in settings.free_trial_whitelist
        has_used_trial = await users_repo.get_user_trial_status(db, user_id)
        is_trial_available = is_in_whitelist or not has_used_trial

        await cb.message.edit_caption(
            caption=_("Family lineup is ready! Please choose your generation package for the family portrait:"),
            reply_markup=quality_kb(
                generation_type=GenerationType.FAMILY_PHOTO,
                is_trial_available=is_trial_available
            ),
        )
        await state.set_state(Generation.waiting_for_quality)

    except Exception as e:
        business_logger.exception("Failed to start family photo flow", error=e)
        await cb.message.edit_caption(caption=_("Sorry, something went wrong. Please /start over."), reply_markup=None)
        await state.clear()
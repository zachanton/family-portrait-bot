# aiogram_bot_template/handlers/next_step_handler.py
import asyncpg
import structlog
from aiogram import F, Router
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

    await _cleanup_selection_messages(callback.bot, callback.message.chat.id, state)
    
    with suppress(TelegramBadRequest):
        await callback.message.delete()
            
    await menu.send_welcome_message(callback.message, state, is_restart=True)


# --- MODIFICATION: Added Generation.child_selected to the StateFilter ---
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
    Handles the "Try again" button from both the post-generation and post-selection screens.
    Re-runs the parameter selection flow using the original parent photos.
    """
    await cb.answer()
    if not cb.message:
        return

    # If the user retries after selecting a child, this will also delete the confirmation message.
    with suppress(TelegramBadRequest):
        await cb.message.delete()
    
    # We now fetch the original request ID from the callback to get parent photos
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
        # Ensure we keep the generation type from the original request
        generation_type=GenerationType.CHILD_GENERATION.value,
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
):
    """
    Handles the selection of a child image.
    - Deletes the shared 'Try Again/Start New' menu.
    - Sends a new message with the selected image and new actions.
    """
    await cb.answer()
    
    if not cb.message:
        business_logger.warning("CallbackQuery without a message received in process_continue_with_image")
        return

    chat_id = cb.message.chat.id
    
    with suppress(TelegramBadRequest):
        await cb.bot.delete_message(chat_id=chat_id, message_id=callback_data.next_step_message_id)

    db = PostgresConnection(db_pool, logger=business_logger)
    sql = "SELECT result_file_id FROM generations WHERE id = $1"
    result = await db.fetchrow(sql, (callback_data.generation_id,))
    
    if not result or not result.data or not result.data.get("result_file_id"):
        await cb.message.answer(_("I couldn't find the selected image. Please start over using /start."))
        await state.clear()
        return

    selected_file_id = result.data["result_file_id"]

    await cb.bot.send_photo(
        chat_id=chat_id,
        photo=selected_file_id,
        caption=_("You've selected this child. What would you like to do next?"),
        reply_markup=child_selection_kb.post_child_selection_kb(
            generation_id=callback_data.generation_id,
            request_id=callback_data.request_id
        )
    )
    
    await state.set_state(Generation.child_selected)
    await state.update_data(next_step_message_id=None)

@router.callback_query(CreateFamilyPhotoCallback.filter(), StateFilter(Generation.child_selected))
async def process_create_family_photo(
    cb: CallbackQuery,
    callback_data: CreateFamilyPhotoCallback,
    state: FSMContext,
    db_pool: asyncpg.Pool,
    business_logger: structlog.typing.FilteringBoundLogger,
):
    """
    Initiates the family photo generation flow.
    It now correctly checks for trial availability before showing the quality keyboard.
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
        # 1. Get parent photos from the original request
        parent_request = await generations_repo.get_request_details_with_sources(db, callback_data.parent_request_id)
        if not parent_request or len(parent_request.get("source_images", [])) < 2:
            raise ValueError("Could not find original parent photos.")
            
        parent_sources = parent_request["source_images"]
        father_source = next((img for img in parent_sources if img.get('role') == ImageRole.FATHER.value), parent_sources[0])
        mother_source = next((img for img in parent_sources if img.get('role') == ImageRole.MOTHER.value), parent_sources[1])
        father_source['role'] = ImageRole.FATHER.value
        mother_source['role'] = ImageRole.MOTHER.value

        # 2. Get the selected child's photo
        sql_child = "SELECT result_image_unique_id, result_file_id FROM generations WHERE id = $1"
        child_res = await db.fetchrow(sql_child, (callback_data.child_generation_id,))
        if not child_res.data:
            raise ValueError("Could not find the selected child's image data.")
        
        child_source = {
            "file_unique_id": child_res.data["result_image_unique_id"],
            "file_id": child_res.data["result_file_id"],
            "role": ImageRole.CHILD.value,
        }

        # 3. Assemble sources for the new request
        all_sources = [father_source, mother_source, child_source]
        source_images_dto = [(img["file_unique_id"], img["file_id"], img["role"]) for img in all_sources]

        # 4. Create a new generation request in the DB
        draft = generations_repo.GenerationRequestDraft(
            user_id=user_id, status="params_collected", source_images=source_images_dto
        )
        new_request_id = await generations_repo.create_generation_request(db, draft)
        
        # 5. Update state for the generation worker
        await state.update_data(
            request_id=new_request_id,
            generation_type=GenerationType.FAMILY_PHOTO.value,
            photos_collected=all_sources
        )

        is_in_whitelist = user_id in settings.free_trial_whitelist
        has_used_trial = await users_repo.get_user_trial_status(db, user_id)
        is_trial_available = is_in_whitelist or not has_used_trial

        # 6. Proceed to quality selection (payment)
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
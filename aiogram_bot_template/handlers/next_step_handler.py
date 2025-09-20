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
from aiogram_bot_template.data.constants import GenerationType
from aiogram_bot_template.db.db_api.storages import PostgresConnection
from aiogram_bot_template.db.repo import generations as generations_repo
from aiogram_bot_template.keyboards.inline.callbacks import RetryGenerationCallback, ContinueWithImageCallback
from aiogram_bot_template.keyboards.inline import child_selection as child_selection_kb
from aiogram_bot_template.keyboards.inline.gender import gender_kb
from aiogram_bot_template.states.user import Generation
# Import the cleanup helper
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

    # Cleanup is CORRECT here because we start a completely new session.
    await _cleanup_selection_messages(callback.bot, callback.message.chat.id, state)
    
    with suppress(TelegramBadRequest):
        await callback.message.delete()
            
    await menu.send_welcome_message(callback.message, state, is_restart=True)


@router.callback_query(RetryGenerationCallback.filter(), StateFilter(Generation.waiting_for_next_action))
async def process_retry_generation(
    cb: CallbackQuery,
    callback_data: RetryGenerationCallback,
    state: FSMContext,
    db_pool: asyncpg.Pool,
    business_logger: structlog.typing.FilteringBoundLogger
):
    """
    Handles the "Try again" button. Re-runs the parameter selection flow
    without cleaning up previously generated child images.
    """
    await cb.answer()
    
    if not cb.message:
        return

    # --- CHANGE: The cleanup function is no longer called here. ---
    # The old child selection buttons will remain active.
    
    # We only delete the message containing the "Try Again" button itself.
    with suppress(TelegramBadRequest):
        await cb.message.delete()

    db = PostgresConnection(db_pool, logger=business_logger)
    
    original_request = await generations_repo.get_request_details_with_sources(db, callback_data.request_id)
    if not original_request or not original_request.get("source_images"):
        await cb.message.answer(_("Could not find the original photos. Please start over with /start."))
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

    # We don't clear the state completely, just set the new state and update the request ID.
    # The photo_message_ids from the previous run remain, which is what we want.
    await state.set_state(Generation.choosing_child_gender)
    await state.update_data(
        request_id=new_request_id,
        # Keep old photos in state for the new request
        photos_collected=[
            {"file_id": img[1], "file_unique_id": img[0]} 
            for img in source_images_dto
        ],
        is_retry=True,
        generation_type=original_request.get("type", GenerationType.CHILD_GENERATION.value),
        # Remove the ID of the deleted "Try Again" menu message
        next_step_message_id=None
    )

    await cb.message.answer(
        _("Let's try again! Please choose the desired gender for your child:"),
        reply_markup=gender_kb()
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
    - All original 'Continue with...' buttons remain unchanged until a new session is started.
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


@router.callback_query(F.data.startswith("group_photo_w_child:"), StateFilter(Generation.child_selected))
async def process_group_photo_with_child_placeholder(cb: CallbackQuery):
    """Placeholder for the 'Create group photo' feature."""
    await cb.answer()
    if cb.message:
        await cb.message.edit_text(
            _("This feature is coming soon! For now, you can /start a new generation."),
            reply_markup=None
        )
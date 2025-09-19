# aiogram_bot_template/handlers/next_step_handler.py
import asyncpg
import structlog
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from aiogram.filters import StateFilter
from aiogram.utils.i18n import gettext as _
from . import menu

from aiogram_bot_template.data.constants import GenerationType
from aiogram_bot_template.db.db_api.storages import PostgresConnection
from aiogram_bot_template.db.repo import generations as generations_repo
from aiogram_bot_template.keyboards.inline.callbacks import RetryGenerationCallback
from aiogram_bot_template.keyboards.inline.gender import gender_kb
from aiogram_bot_template.states.user import Generation


router = Router(name="next-step-handler")

@router.callback_query(F.data == "start_new", StateFilter("*"))
async def start_new_generation(
    callback: CallbackQuery,
    state: FSMContext,
):
    await callback.answer()
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
    Handles the "Try again" button. It reuses the original photos but
    sends the user back to the beginning of the parameter selection flow.
    """
    await cb.answer()
    await cb.message.delete()

    db = PostgresConnection(db_pool, logger=business_logger)
    
    # 1. Fetch the original request to get the source photos
    original_request = await generations_repo.get_request_details_with_sources(db, callback_data.request_id)
    if not original_request or not original_request.get("source_images"):
        await cb.message.answer(_("Could not find the original photos. Please start over with /start."))
        return
    
    # 2. Prepare data for a new request using old photos
    source_images_dto = [
        (img["file_unique_id"], img["file_id"], img["role"])
        for img in original_request["source_images"]
    ]
    
    # 3. Create a new request in the DB to track this retry attempt separately
    draft = generations_repo.GenerationRequestDraft(
        user_id=cb.from_user.id,
        status="photos_collected", # We start from the state after photo collection
        source_images=source_images_dto,
    )
    new_request_id = await generations_repo.create_generation_request(db, draft)

    # 4. Reset the FSM state and prepare it for the new parameter selection flow
    await state.clear()
    await state.set_state(Generation.choosing_child_gender)
    await state.update_data(
        request_id=new_request_id,
        photos_collected=[
            {"file_id": img[1], "file_unique_id": img[0]} 
            for img in source_images_dto
        ],
        is_retry=True,
        # Store the generation type so we know what to do later
        generation_type=original_request.get("type", GenerationType.CHILD_GENERATION.value)
    )

    # 5. Send the first message of the parameter selection flow
    await cb.message.answer(
        _("Let's try again! Please choose the desired gender for your child:"),
        reply_markup=gender_kb()
    )
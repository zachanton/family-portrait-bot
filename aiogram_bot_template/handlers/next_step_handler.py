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
from aiogram_bot_template.db.repo import generations as generations_repo, users as users_repo
from aiogram_bot_template.keyboards.inline.callbacks import RetryGenerationCallback
from aiogram_bot_template.keyboards.inline.quality import quality_kb
from aiogram_bot_template.data.settings import settings
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

@router.callback_query(RetryGenerationCallback.filter(), StateFilter("*"))
async def process_retry_generation(
    cb: CallbackQuery,
    callback_data: RetryGenerationCallback,
    state: FSMContext,
    db_pool: asyncpg.Pool,
    business_logger: structlog.typing.FilteringBoundLogger
):
    await cb.answer()
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

    await state.clear()
    await state.set_state(Generation.waiting_for_quality)
    await state.update_data(
        request_id=new_request_id,
        photos_collected=[
            {"file_id": img[1], "file_unique_id": img[0]} 
            for img in source_images_dto
        ],
        is_retry=True,
    )

    user_id = cb.from_user.id
    is_in_whitelist = user_id in settings.free_trial_whitelist
    has_used_trial = await users_repo.get_user_trial_status(db, user_id)
    is_trial_available = is_in_whitelist or not has_used_trial
    
    await cb.message.answer(
        _("Let's try another variation! Please select the quality for the new portrait:"),
        reply_markup=quality_kb(is_trial_available)
    )
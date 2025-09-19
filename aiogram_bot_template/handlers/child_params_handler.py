# aiogram_bot_template/handlers/child_params_handler.py
import asyncpg
import structlog
from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from aiogram.filters import StateFilter
from aiogram.utils.i18n import gettext as _
from contextlib import suppress
from aiogram.exceptions import TelegramBadRequest

from aiogram_bot_template.data.constants import GenerationType
from aiogram_bot_template.db.db_api.storages import PostgresConnection
from aiogram_bot_template.db.repo import generations as generations_repo, users as users_repo
from aiogram_bot_template.keyboards.inline.callbacks import (
    ChildGenderCallback, ChildAgeCallback, ChildResemblanceCallback
)
from aiogram_bot_template.keyboards.inline.age import age_kb
from aiogram_bot_template.keyboards.inline.resemblance import resemblance_kb
from aiogram_bot_template.keyboards.inline.quality import quality_kb
from aiogram_bot_template.states.user import Generation
from aiogram_bot_template.data.settings import settings

router = Router(name="child-params-handler")

@router.callback_query(ChildGenderCallback.filter(), StateFilter(Generation.choosing_child_gender))
async def process_gender_selection(
    cb: CallbackQuery,
    callback_data: ChildGenderCallback,
    state: FSMContext,
) -> None:
    """Handles gender selection and asks for age."""
    await cb.answer()
    await state.update_data(child_gender=callback_data.gender)
    await state.set_state(Generation.choosing_child_age)
    
    with suppress(TelegramBadRequest):
        await cb.message.edit_text(
            _("Next, choose the age category:"),
            reply_markup=age_kb()
        )

@router.callback_query(ChildAgeCallback.filter(), StateFilter(Generation.choosing_child_age))
async def process_age_selection(
    cb: CallbackQuery,
    callback_data: ChildAgeCallback,
    state: FSMContext,
) -> None:
    """Handles age selection and asks for resemblance."""
    await cb.answer()
    await state.update_data(child_age=callback_data.age)
    await state.set_state(Generation.choosing_child_resemblance)

    with suppress(TelegramBadRequest):
        await cb.message.edit_text(
            _("Finally, who should the child resemble more?"),
            reply_markup=resemblance_kb()
        )

@router.callback_query(ChildResemblanceCallback.filter(), StateFilter(Generation.choosing_child_resemblance))
async def process_resemblance_selection(
    cb: CallbackQuery,
    callback_data: ChildResemblanceCallback,
    state: FSMContext,
    db_pool: asyncpg.Pool,
    business_logger: structlog.typing.FilteringBoundLogger,
) -> None:
    """
    Finalizes parameter collection, creates a request in the DB,
    and proceeds to quality selection.
    """
    await cb.answer()
    await state.update_data(child_resemblance=callback_data.resemblance)
    
    user_data = await state.get_data()
    db = PostgresConnection(db_pool, logger=business_logger)
    user_id = cb.from_user.id

    # Create a DB record for this generation request
    photos = user_data.get("photos_collected", [])
    source_images_dto = [(p["file_unique_id"], p["file_id"], f"photo_{i+1}") for i, p in enumerate(photos)]
    
    draft = generations_repo.GenerationRequestDraft(
        user_id=user_id, status="params_collected", source_images=source_images_dto
    )
    request_id = await generations_repo.create_generation_request(db, draft)
    await state.update_data(
        request_id=request_id,
        generation_type=GenerationType.CHILD_GENERATION.value # Store the type for the worker
    )

    # Check for free trial availability
    is_in_whitelist = user_id in settings.free_trial_whitelist
    has_used_trial = await users_repo.get_user_trial_status(db, user_id)
    is_trial_available = is_in_whitelist or not has_used_trial

    with suppress(TelegramBadRequest):
        await cb.message.edit_text(
            _("Excellent! All parameters are set. Please choose your generation package:"),
            reply_markup=quality_kb(
                generation_type=GenerationType.CHILD_GENERATION, # Explicitly pass the type
                is_trial_available=is_trial_available
            ),
        )

    await state.set_state(Generation.waiting_for_quality)
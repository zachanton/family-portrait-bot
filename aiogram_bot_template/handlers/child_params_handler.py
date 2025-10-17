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
            _("Great! Now, let's choose an age for your child:"),
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
            _("Almost there! Who should the child resemble more?"),
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
    Finalizes parameter collection and proceeds to quality selection.
    The generation_request is now created in the photo_handler.
    """
    await cb.answer()
    await state.update_data(child_resemblance=callback_data.resemblance)
    
    user_data = await state.get_data()
    db = PostgresConnection(db_pool, logger=business_logger)
    user_id = cb.from_user.id
    request_id = user_data.get("request_id")

    # The request is already created, we just update its status
    if request_id:
        await generations_repo.update_generation_request_status(db, request_id, "params_collected")
    else:
        # This is a fallback, but ideally should not happen in the new flow
        business_logger.error("request_id not found in state during resemblance selection.")
        await cb.message.edit_text(_("An error occurred. Please /start over."))
        await state.clear()
        return

    await state.update_data(
        generation_type=GenerationType.CHILD_GENERATION.value
    )

    is_in_whitelist = user_id in settings.free_trial_whitelist
    has_used_queue = await users_repo.get_user_live_queue_status(db, user_id)

    with suppress(TelegramBadRequest):
        await cb.message.edit_text(
            _("✨ Excellent! Everything is set. \n\nNow, please choose a package:"),
            reply_markup=quality_kb(
                generation_type=GenerationType.CHILD_GENERATION,
                is_trial_available=is_in_whitelist,
                is_live_queue_available=not has_used_queue
            ),
        )

    await state.set_state(Generation.waiting_for_quality)
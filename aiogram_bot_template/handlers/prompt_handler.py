# aiogram_bot_template/handlers/prompt_handler.py
import asyncpg
import structlog

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from aiogram.utils.i18n import gettext as _

from aiogram_bot_template.states.user import Generation
from aiogram_bot_template.utils import moderation
from aiogram_bot_template.keyboards.inline import quality, confirm
from aiogram_bot_template.db.db_api.storages import PostgresConnection
from aiogram_bot_template.db.repo import users as users_repo
from aiogram_bot_template.data.settings import settings


router = Router(name="prompt-handler")


@router.message(Generation.waiting_for_prompt, F.text)
async def process_prompt(
    message: Message,
    state: FSMContext,
) -> None:
    """
    Receives user's text, saves it as a candidate, and asks for confirmation.
    """
    original_prompt = message.text

    if not await moderation.is_safe_prompt(original_prompt):
        await message.answer(
            _("🚫 This request is prohibited by the service rules.\nPlease try to rephrase it.")
        )
        return

    data = await state.get_data()
    continue_key = data.get("continue_key")
    request_id = data.get("original_request_id")

    # This check makes the flow robust against unexpected state transitions.
    if not continue_key or not request_id:
        await message.answer(_("An error occurred with the session. Please start over using /cancel."))
        return

    await state.update_data(user_prompt_candidate=original_prompt)

    await message.answer(
        _("Got it. You want to: «{prompt}»\n\nIs that correct?").format(prompt=original_prompt),
        reply_markup=confirm.create_user_prompt_confirm_kb(
            continue_key=continue_key, request_id=request_id
        )
    )
    await state.set_state(Generation.waiting_for_user_prompt_confirm)


@router.callback_query(Generation.waiting_for_user_prompt_confirm, F.data == "user_prompt_no")
async def confirm_user_prompt_no(call: CallbackQuery, state: FSMContext) -> None:
    await call.answer()
    await call.message.edit_text(_("No problem. Please describe the edit you'd like to make again:"))
    await state.set_state(Generation.waiting_for_prompt)


@router.callback_query(Generation.waiting_for_user_prompt_confirm, F.data == "user_prompt_yes")
async def confirm_user_prompt_yes(
    call: CallbackQuery,
    state: FSMContext,
    db_pool: asyncpg.Pool,
    business_logger: structlog.typing.FilteringBoundLogger
) -> None:
    """
    Saves the confirmed prompt to the state and proceeds to quality selection.
    The enhancement is now done within the pipeline.
    """
    await call.answer()
    data = await state.get_data()

    original_prompt = data.get("user_prompt_candidate")
    if not original_prompt:
        await call.message.edit_text(_("An error occurred with your session. Please try again with /cancel."))
        return

    # Just save the original text. The pipeline will handle enhancement.
    await state.update_data(original_prompt_text=original_prompt)

    db = PostgresConnection(db_pool, logger=business_logger)
    user_id = call.from_user.id

    is_in_whitelist = user_id in settings.free_trial_whitelist
    has_used_trial = await users_repo.get_user_trial_status(db, user_id)
    is_trial_available = is_in_whitelist or not has_used_trial

    continue_key = data.get("continue_key")
    request_id = data.get("original_request_id")

    await call.message.edit_text(
        _("Great! Now, please select the generation quality (the price is shown on each button):"),
        reply_markup=quality.quality_kb(
            is_trial_available=is_trial_available,
            continue_key=continue_key,
            request_id=request_id
        ),
    )
    await state.set_state(Generation.waiting_for_quality)


@router.message(Generation.waiting_for_prompt, ~F.text)
async def expect_text_for_prompt(message: Message) -> None:
    await message.answer(_("I'm waiting for a text description. Please tell me what to change."))

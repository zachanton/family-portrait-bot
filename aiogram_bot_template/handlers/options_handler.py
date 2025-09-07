# aiogram_bot_template/handlers/options_handler.py
import asyncio
import structlog
import asyncpg
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from aiogram.utils.i18n import gettext as _
from aiogram.utils.i18n import I18n

from aiogram_bot_template.keyboards.inline import (
    generation_quality,
    edit_prompts,
    quality,
    next_step,
)
from aiogram_bot_template.keyboards.inline.callbacks import (
    AgeSelectionCallback,
    GenderSelectionCallback,
    LikenessSelectionCallback,
    EditMenuCallback,
)
from aiogram_bot_template.keyboards.inline.child_age import (
    gender_selection_kb,
    likeness_selection_kb,
)
from aiogram_bot_template.states.user import Generation
from aiogram_bot_template.keyboards.inline.callbacks import BackToPromptSelection
from aiogram_bot_template.utils import re_prompt
from aiogram_bot_template.db.db_api.storages import PostgresConnection
from aiogram_bot_template.db.repo import generations as generations_repo
from aiogram_bot_template.db.repo import users as users_repo
from aiogram_bot_template.data.settings import settings
from aiogram_bot_template.data.constants import GenerationType
from aiogram_bot_template.dto.generation_parameters import GenerationParameters
from aiogram_bot_template.dto.prompt_suggestions import ALL_PROMPT_SUGGESTIONS
from aiogram_bot_template.dto.facial_features import ImageDescription
from contextlib import suppress
from aiogram.exceptions import TelegramBadRequest


router = Router(name="options-handler")


# These handlers are fast, no background task needed.
@router.callback_query(Generation.waiting_for_options, AgeSelectionCallback.filter())
async def process_age_selection(
    callback: CallbackQuery, callback_data: AgeSelectionCallback, state: FSMContext
) -> None:
    await state.update_data(age_group=callback_data.age_group)
    await callback.message.edit_text(
        _("Wonderful! Who are we expecting?"),
        reply_markup=gender_selection_kb(),
    )
    await callback.answer()


@router.callback_query(Generation.waiting_for_options, GenderSelectionCallback.filter())
async def process_gender_selection(
    callback: CallbackQuery, callback_data: GenderSelectionCallback, state: FSMContext
) -> None:
    await state.update_data(gender=callback_data.gender)
    await callback.message.edit_text(
        _("Almost done! Who should the child take after more?"),
        reply_markup=likeness_selection_kb(),
    )
    await callback.answer()


async def _process_likeness_selection_async(
    callback: CallbackQuery,
    callback_data: LikenessSelectionCallback,
    state: FSMContext,
    db_pool: asyncpg.Pool,
    business_logger: structlog.typing.FilteringBoundLogger,
):
    await state.update_data(resemble=callback_data.resemble)

    user_data = await state.get_data()

    db = PostgresConnection(db_pool, logger=business_logger)
    request_id = user_data.get("request_id")
    if request_id:
        params_dto = GenerationParameters.from_fsm_data(user_data)
        await generations_repo.update_request_parameters(db, request_id, params_dto)
        await generations_repo.update_generation_request_status(db, request_id, "options_selected")

    user_id = callback.from_user.id

    is_in_whitelist = user_id in settings.free_trial_whitelist
    has_used_trial = await users_repo.get_user_trial_status(db, user_id)
    is_trial_available = is_in_whitelist or not has_used_trial

    age_group = user_data.get("age_group")
    
    # Map internal age group keys to translatable strings
    age_map = {
        "baby": ("👶", _("Baby (0-2)")), 
        "child": ("🧒", _("Child (5-10)")), 
        "teen": ("🧑", _("Teenager (13-18)"))
    }
    age_emoji, age_text = age_map.get(age_group, ("🧒", _("Child (5-10)")))

    gender, resemble = user_data.get("gender"), user_data.get("resemble")

    # Wrap the data values in the translation function `_()`
    summary_text = _(
        "<b>Excellent! Here is your configuration:</b>\n\n"
        "{age_icon} <b>Age Group:</b> {age}\n\n"
        "⚤ <b>Gender:</b> {gender}\n\n"
        "👪 <b>Resembles:</b> {resemble}\n\n"
        "Now, please choose the quality for your generation."
    ).format(age_icon=age_emoji, age=age_text, gender=_(gender.capitalize()), resemble=_(resemble.capitalize()))

    continue_key = user_data.get("continue_key")

    if callback.message:
        await callback.message.edit_text(
            summary_text,
            reply_markup=generation_quality.generation_quality_kb(
                is_trial_available=is_trial_available,
                generation_type=GenerationType(user_data.get("generation_type")),
                continue_key=continue_key,
                request_id=request_id
            ),
        )

    await state.set_state(Generation.waiting_for_quality)


async def _navigate_edit_menu_async(
    cb: CallbackQuery, callback_data: EditMenuCallback, state: FSMContext
):
    data = await state.get_data()

    continue_key = data.get("continue_key")
    request_id = data.get("original_request_id")
    
    # Retrieve the source generation type from the FSM state
    source_gen_type_str = data.get("source_generation_type_for_edit")
    # Default to CHILD_GENERATION if it's somehow missing, to prevent errors
    source_gen_type = GenerationType(source_gen_type_str) if source_gen_type_str else GenerationType.CHILD_GENERATION

    child_desc_model = ImageDescription.model_validate(data["child_description"]) if data.get("child_description") else None

    markup = edit_prompts.create_edit_menu_kb(
        back_continue_key=continue_key,
        back_request_id=request_id,
        child_description=child_desc_model,
        parent_descriptions=data.get("parent_descriptions"),
        generation_type=source_gen_type,
        path=callback_data.path
    )

    if cb.message:
        with suppress(TelegramBadRequest):
            await cb.message.edit_text(
                _("Choose a category or an option to edit your image:"),
                reply_markup=markup
            )


async def _process_prompt_suggestion_async(
    call: CallbackQuery,
    state: FSMContext,
    db_pool: asyncpg.Pool,
    business_logger: structlog.typing.FilteringBoundLogger
):
    """
    Handles a predefined prompt suggestion. Saves the raw prompt text to the state
    and proceeds to quality selection.
    """
    suggestion_key = call.data.split(":", 1)[1]

    if suggestion_key == "custom":
        if call.message:
            await call.message.edit_text(_("📝 Okay, enter the text prompt manually."))
        await state.set_state(Generation.waiting_for_prompt)
        return

    suggestion = ALL_PROMPT_SUGGESTIONS.get(suggestion_key)
    if not suggestion:
        if call.message:
            await call.message.edit_text(_("An error occurred with this suggestion. Please enter a prompt manually."))
        await state.set_state(Generation.waiting_for_prompt)
        return

    await state.update_data(
        original_prompt_text=_(suggestion.text),
        prompt_for_enhancer=suggestion.prompt_for_enhancer
    )

    db = PostgresConnection(db_pool, logger=business_logger)
    user_id = call.from_user.id

    is_in_whitelist = user_id in settings.free_trial_whitelist
    has_used_trial = await users_repo.get_user_trial_status(db, user_id)
    is_trial_available = is_in_whitelist or not has_used_trial

    data = await state.get_data()
    continue_key = data.get("continue_key")
    request_id = data.get("original_request_id")

    if call.message:
        await call.message.edit_text(
            _("Got it. Now choose the generation quality (price is on the button):"),
            reply_markup=quality.quality_kb(
                is_trial_available=is_trial_available,
                continue_key=continue_key,
                request_id=request_id
            ),
        )
    await state.set_state(Generation.waiting_for_quality)


async def _back_to_prompt_selection_async(
    cb: CallbackQuery, callback_data: BackToPromptSelection, state: FSMContext, i18n: I18n
):
    data = await state.get_data()
    continue_key = data.get("continue_key")
    request_id = data.get("request_id")

    if continue_key and request_id:
        gen_type = GenerationType(data.get("generation_type", GenerationType.CHILD_GENERATION))
        markup = next_step.get_next_step_keyboard(gen_type, continue_key, request_id)
        if cb.message: await cb.message.edit_text(_("What would you like to do next?"), reply_markup=markup)
        await state.set_state(Generation.waiting_for_next_action)

    elif getattr(callback_data, "is_child_gen", False):
        await state.set_state(Generation.waiting_for_options)
        if cb.message: await re_prompt.re_prompt_for_state(state, cb.message, i18n)

    else:
        await state.set_state(Generation.waiting_for_prompt)
        if cb.message: await re_prompt.re_prompt_for_state(state, cb.message, i18n)


@router.callback_query(Generation.waiting_for_options, LikenessSelectionCallback.filter())
async def process_likeness_selection(
    callback: CallbackQuery,
    callback_data: LikenessSelectionCallback,
    state: FSMContext,
    db_pool: asyncpg.Pool,
    business_logger: structlog.typing.FilteringBoundLogger,
):
    with suppress(TelegramBadRequest): await callback.answer()
    asyncio.create_task(
        _process_likeness_selection_async(callback, callback_data, state, db_pool, business_logger)
    )


@router.callback_query(EditMenuCallback.filter())
async def navigate_edit_menu(
    cb: CallbackQuery, callback_data: EditMenuCallback, state: FSMContext
):
    with suppress(TelegramBadRequest): await cb.answer()
    asyncio.create_task(_navigate_edit_menu_async(cb, callback_data, state))


@router.callback_query(F.data.startswith("prompt_suggestion:"))
async def process_prompt_suggestion(
    call: CallbackQuery,
    state: FSMContext,
    db_pool: asyncpg.Pool,
    business_logger: structlog.typing.FilteringBoundLogger
):
    with suppress(TelegramBadRequest): await call.answer()
    asyncio.create_task(
        _process_prompt_suggestion_async(call, state, db_pool, business_logger)
    )


@router.callback_query(BackToPromptSelection.filter())
async def back_to_prompt_selection(
    cb: CallbackQuery, callback_data: BackToPromptSelection, state: FSMContext, i18n: I18n
):
    with suppress(TelegramBadRequest): await cb.answer()
    asyncio.create_task(_back_to_prompt_selection_async(cb, callback_data, state, i18n))

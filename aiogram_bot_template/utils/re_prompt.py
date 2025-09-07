# aiogram_bot_template/utils/re_prompt.py
from collections.abc import Awaitable, Callable
from typing import Any
from contextlib import suppress

from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram.utils.i18n import I18n, gettext as _
from aiogram.exceptions import TelegramBadRequest

from aiogram_bot_template.data.constants import GenerationType
from aiogram_bot_template.keyboards.inline import (
    generation_quality,
    feedback,
    quality,
    next_step,
    child_age,
    edit_prompts,
)
from aiogram_bot_template.states.user import Generation
from aiogram_bot_template.data import message_provider
from aiogram_bot_template.dto.facial_features import ImageDescription


async def _prompt_for_collecting_inputs(
    message: Message, state: FSMContext, **_kwargs: Any
) -> None:
    """Sends the prompt for the photo collection state, using original texts."""
    data = await state.get_data()
    photos_collected = len(data.get("photos_collected", []))
    text = ""

    # This logic now mirrors the original handlers in menu.py and photo_handler.py
    if data.get("generation_type") == GenerationType.CHILD_GENERATION:
        if photos_collected == 0:
            text = message_provider.get_start_message()
        else:
            text = _("Got it. Please send the second parent's photo now.")
    else:  # For image_edit
        text = _(
            "Thank you! Now, please describe what you'd like to change (e.g., 'change the background to a cyberpunk style')."
        )

    with suppress(TelegramBadRequest):
        await message.edit_text(text, reply_markup=None)


async def _prompt_for_waiting_prompt(
    message: Message, state: FSMContext, **_kwargs: Any
) -> None:
    """Sends the prompt to wait for a text description, with the suggestions keyboard."""
    data = await state.get_data()

    # This logic mirrors the handler in next_step_handler.py
    continue_key = data.get("continue_key")
    request_id = data.get("original_request_id")
    child_desc_model = ImageDescription.model_validate(data["child_description"]) if data.get("child_description") else None

    reply_markup = edit_prompts.create_edit_menu_kb(
        back_continue_key=continue_key,
        back_request_id=request_id,
        child_description=child_desc_model,
        parent_descriptions=data.get("parent_descriptions"),
        path=None,  # We are at the top level of the menu
    )

    with suppress(TelegramBadRequest):
        await message.edit_text(
            _(
                "Ready to get creative! Please describe your edit, or choose a suggestion below:"
            ),
            reply_markup=reply_markup,
        )


async def _prompt_for_waiting_quality(
    message: Message, state: FSMContext, **_kwargs: Any
) -> None:
    """Sends the prompt for quality selection, mirroring original handlers."""
    data = await state.get_data()
    gen_type = data.get("generation_type")

    # Logic mirrors handlers in options_handler.py and prompt_handler.py
    if gen_type == GenerationType.IMAGE_EDIT:
        markup = quality.quality_kb()
        text = _("Great! Now, please select the generation quality (the price is shown on each button):")
    else:  # child_generation
        markup = generation_quality.generation_quality_kb()
        text = _("All set! Finally, please select the generation quality:")

    with suppress(TelegramBadRequest):
        await message.edit_text(text, reply_markup=markup)


async def _prompt_for_waiting_options(message: Message, **_kwargs: Any) -> None:
    """Sends the prompt for option selection, mirroring photo_handler.py."""
    with suppress(TelegramBadRequest):
        await message.edit_text(
            _(
                "Excellent, both photos are uploaded.\n\n"
                "Next, please choose the desired age group for the child:"
            ),
            reply_markup=child_age.age_selection_kb(),
        )


async def _prompt_for_feedback(message: Message, state: FSMContext, **_kwargs: Any) -> None:
    """Sends the prompt for the feedback state, mirroring generation_worker.py."""
    data = await state.get_data()
    generation_id = data.get("feedback_generation_id")
    continue_key = data.get("feedback_continue_key", "expired")

    if not generation_id:
        await state.clear()
        await state.set_state(Generation.collecting_inputs)
        await _prompt_for_collecting_inputs(message=message, state=state, **_kwargs)
        return

    # Text mirrors what user sees before feedback buttons appear.
    caption = message.caption or ""  # Keep original caption if possible
    with suppress(TelegramBadRequest):
        await message.edit_caption(
            caption=caption,
            reply_markup=feedback.feedback_kb(generation_id, continue_key),
        )


async def _prompt_for_next_action(
    message: Message, state: FSMContext, **_kwargs: Any
) -> None:
    """Sends the prompt for the 'what to do next?' state, mirroring generation_worker.py."""
    data = await state.get_data()
    gen_type_str = data.get("generation_type")
    gen_id = data.get("generation_id")
    continue_key = data.get("continue_key", "expired")

    if not all([gen_type_str, gen_id, continue_key]):
        await state.clear()
        await state.set_state(Generation.collecting_inputs)
        await _prompt_for_collecting_inputs(message=message, state=state, **_kwargs)
        return

    gen_type = GenerationType(gen_type_str)
    reply_markup = next_step.get_next_step_keyboard(gen_type, continue_key, gen_id)

    # Text now mirrors the text from feedback_handler.py, which is the final step
    # before this state is set.
    text_to_edit = _("Thank you! What would you like to do next?")

    with suppress(TelegramBadRequest):
        if message.photo or message.document:
            await message.edit_caption(caption=text_to_edit, reply_markup=reply_markup)
        else:
            await message.edit_text(text_to_edit, reply_markup=reply_markup)


# Map of states to their corresponding prompters
STATE_PROMPTERS: dict[str | None, Callable[..., Awaitable[None]]] = {
    Generation.collecting_inputs.state: _prompt_for_collecting_inputs,
    Generation.waiting_for_prompt.state: _prompt_for_waiting_prompt,
    Generation.waiting_for_quality.state: _prompt_for_waiting_quality,
    Generation.waiting_for_options.state: _prompt_for_waiting_options,
    Generation.waiting_for_feedback.state: _prompt_for_feedback,
    Generation.waiting_for_next_action.state: _prompt_for_next_action,
}


async def re_prompt_for_state(state: FSMContext, message: Message, i18n: I18n) -> None:
    """
    Re-sends the appropriate prompt for the user's current FSM state.
    If the state is unknown or None, it resets the user to the main flow.
    """
    current_state_str = await state.get_state()
    prompter = STATE_PROMPTERS.get(current_state_str)

    # Make the locale available for all downstream calls
    with i18n.context():
        if not prompter:
            # Fallback to a clean start if the state is invalid or None
            await state.clear()
            # Initialize the state with the same data as the /start command
            await state.update_data(
                generation_type=GenerationType.CHILD_GENERATION,
                photos_needed=2,
                photos_collected=[],
            )
            await state.set_state(Generation.collecting_inputs)
            prompter = _prompt_for_collecting_inputs

        with suppress(TelegramBadRequest):
            # Pass all necessary context to the prompter
            await prompter(message=message, i18n=i18n, state=state)
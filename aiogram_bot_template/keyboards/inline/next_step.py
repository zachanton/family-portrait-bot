# File: aiogram_bot_template/keyboards/inline/next_step.py
import structlog
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.i18n import gettext as _
from .callbacks import (
    ContinueEditingCallback, GetHdCallback, RetryGenerationCallback,
    EditChildParamsCallback, ShowNextStepSubmenu, ReturnToMainMenu,
    CreateGroupPhotoCallback, ReturnToGenerationCallback
)
from aiogram_bot_template.data.constants import GenerationType, SessionContextType

logger = structlog.get_logger(__name__)


def improve_submenu_kb(continue_key: str, request_id: int) -> InlineKeyboardMarkup:
    """Sub-keyboard for 'Improve this result' options."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=_("✏️ Edit Image"), callback_data=ContinueEditingCallback(key=continue_key).pack())],
        [InlineKeyboardButton(text=_("✨ Get HD Version"), callback_data=GetHdCallback(key=continue_key).pack())],
        [InlineKeyboardButton(text=_("⬅️ Back to Options"), callback_data=ReturnToMainMenu(key=continue_key, request_id=request_id).pack())],
    ])


def retry_submenu_kb(continue_key: str, request_id: int) -> InlineKeyboardMarkup:
    """Sub-keyboard for 'Try again' options."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=_("🔁 Another Variation"), callback_data=RetryGenerationCallback(request_id=request_id).pack())],
        [InlineKeyboardButton(text=_("⚙️ Change Age/Gender"), callback_data=EditChildParamsCallback(request_id=request_id).pack())],
        [InlineKeyboardButton(text=_("⬅️ Back to Options"), callback_data=ReturnToMainMenu(key=continue_key, request_id=request_id).pack())],
    ])


def get_return_to_generation_kb(generation_id: int) -> InlineKeyboardMarkup:
    """Creates a simple keyboard with one button to return to a specific generation."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=_("⬅️ Return to this Generation"),
                callback_data=ReturnToGenerationCallback(generation_id=generation_id).pack()
            )
        ]
    ])

# --- SCENARIO KEYBOARDS ---

def _scenario_a_child_gen_kb(continue_key: str, request_id: int) -> InlineKeyboardMarkup:
    """Scenario A: Keyboard for CHILD_GENERATION. Full options: retry, improve, create group photo."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=_("🔁 Try Again"), callback_data=ShowNextStepSubmenu(menu="retry", key=continue_key, request_id=request_id).pack())],
        [InlineKeyboardButton(text=_("✨ Improve This Result"), callback_data=ShowNextStepSubmenu(menu="improve", key=continue_key, request_id=request_id).pack())],
        [InlineKeyboardButton(text=_("🖼️ Create Group Photo"), callback_data=CreateGroupPhotoCallback(key=continue_key).pack())],
        [InlineKeyboardButton(text=_("🔄 Start a New Generation"), callback_data="start_new")],
    ])

def _scenario_b_edited_child_kb(continue_key: str, request_id: int) -> InlineKeyboardMarkup:
    """Scenario B: Keyboard after editing a CHILD portrait. Options: continue improving, create group photo, start new."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=_("✨ Improve This Result"), callback_data=ShowNextStepSubmenu(menu="improve", key=continue_key, request_id=request_id).pack())],
        [InlineKeyboardButton(text=_("🖼️ Create Group Photo"), callback_data=CreateGroupPhotoCallback(key=continue_key).pack())],
        [InlineKeyboardButton(text=_("🔄 Start a New Generation"), callback_data="start_new")],
    ])

def _scenario_c_group_photo_kb(continue_key: str, request_id: int) -> InlineKeyboardMarkup:
    """Scenario C: Keyboard for GROUP_PHOTO. Options: retry variation, improve (edit), start new."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=_("🔁 Another Variation"), callback_data=RetryGenerationCallback(request_id=request_id).pack())],
        [InlineKeyboardButton(text=_("✨ Improve This Result"), callback_data=ShowNextStepSubmenu(menu="improve", key=continue_key, request_id=request_id).pack())],
        [InlineKeyboardButton(text=_("🔄 Start a New Generation"), callback_data="start_new")],
    ])

def _scenario_d_edited_group_photo_kb(continue_key: str, request_id: int) -> InlineKeyboardMarkup:
    """Scenario D: Keyboard after editing a GROUP photo. Options: continue improving, start new."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=_("✨ Improve This Result"), callback_data=ShowNextStepSubmenu(menu="improve", key=continue_key, request_id=request_id).pack())],
        [InlineKeyboardButton(text=_("🔄 Start a New Generation"), callback_data="start_new")],
    ])


# --- Main Dispatcher Function ---

KEYBOARD_SCENARIO_MAP = {
    SessionContextType.CHILD_GENERATION: _scenario_a_child_gen_kb,
    SessionContextType.EDITED_CHILD: _scenario_b_edited_child_kb,
    SessionContextType.GROUP_PHOTO: _scenario_c_group_photo_kb,
    SessionContextType.EDITED_GROUP_PHOTO: _scenario_d_edited_group_photo_kb,
}

def get_next_step_keyboard(
    context: SessionContextType,
    continue_key: str,
    request_id: int,
) -> InlineKeyboardMarkup:
    """
    Returns the correct "next step" keyboard based on the session context.
    """
    logger.info(
        "get_next_step_keyboard called",
        context=context.value if context else "None",
        continue_key=continue_key,
        request_id=request_id,
    )

    # Use the map to find the correct keyboard function, with a fallback to Scenario A
    keyboard_function = KEYBOARD_SCENARIO_MAP.get(context, _scenario_a_child_gen_kb)
    
    return keyboard_function(continue_key, request_id)
# aiogram_bot_template/keyboards/inline/family_selection.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.i18n import gettext as _
from .callbacks import ContinueWithFamilyPhotoCallback


def continue_with_family_photo_kb(
    generation_id: int, request_id: int
) -> InlineKeyboardMarkup:
    """
    Creates a keyboard with a 'Continue with this family portrait' button.

    Args:
        generation_id: The ID of the specific generation this button is attached to.
        request_id: The ID of the parent generation request.

    Returns:
        An inline keyboard.
    """
    buttons = [
        [
            InlineKeyboardButton(
                text=_("❤️ Continue with this portrait"),
                callback_data=ContinueWithFamilyPhotoCallback(
                    generation_id=generation_id,
                    request_id=request_id,
                ).pack(),
            )
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def post_family_photo_selection_kb() -> InlineKeyboardMarkup:
    """
    Creates a keyboard for the final action after selecting a family portrait.
    It only contains a button to start a new generation.

    Returns:
        An inline keyboard with the next action step.
    """
    buttons = [
        [
            InlineKeyboardButton(
                text=_("🔄 Start a New Generation"), callback_data="start_new"
            )
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
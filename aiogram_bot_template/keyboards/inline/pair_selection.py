# aiogram_bot_template/keyboards/inline/pair_selection.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.i18n import gettext as _
from .callbacks import ContinueWithPairPhotoCallback


def continue_with_pair_photo_kb(
    generation_id: int, request_id: int
) -> InlineKeyboardMarkup:
    """
    Creates a keyboard with a 'Continue with this pair portrait' button.

    Args:
        generation_id: The ID of the specific generation this button is attached to.
        request_id: The ID of the parent generation request.

    Returns:
        An inline keyboard.
    """
    buttons = [
        [
            InlineKeyboardButton(
                text=_("❤️ I choose this one!"),
                callback_data=ContinueWithPairPhotoCallback(
                    generation_id=generation_id,
                    request_id=request_id,
                ).pack(),
            )
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def post_pair_photo_selection_kb() -> InlineKeyboardMarkup:
    """
    Creates a keyboard for the final action after selecting a pair portrait.
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
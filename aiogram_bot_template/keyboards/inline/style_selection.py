# aiogram_bot_template/keyboards/inline/style_selection.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.i18n import gettext as _

from .callbacks import StyleCallback


def get_style_selection_button_kb(style_id: str) -> InlineKeyboardMarkup:
    """
    Creates a keyboard with a single 'Select this style' button for a specific style.

    Args:
        style_id: The unique identifier for the style.

    Returns:
        An inline keyboard with one button.
    """
    buttons = [
        [
            InlineKeyboardButton(
                text=_("🎨 Select This Style"),
                callback_data=StyleCallback(style_id=style_id).pack(),
            )
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
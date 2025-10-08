# aiogram_bot_template/keyboards/inline/style_selection.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.i18n import gettext as _

from aiogram_bot_template.services.pipelines.pair_photo_pipeline import styles
from .callbacks import StyleCallback


def style_selection_kb() -> InlineKeyboardMarkup:
    """
    Creates a keyboard for selecting a pair photo style.
    Dynamically generates buttons from the style registry.
    """
    buttons = []
    for style_id, style_info in styles.STYLES.items():
        buttons.append(
            [
                InlineKeyboardButton(
                    text=_(style_info["name"]),
                    callback_data=StyleCallback(style_id=style_id).pack(),
                )
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=buttons)
# aiogram_bot_template/keyboards/inline/aspect_ratio.py
from typing import List
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.i18n import gettext as _
from .callbacks import SelectAspectRatioCallback
from ...utils.chunks import chunks

# This list is the single source of truth for aspect ratios
SUPPORTED_ASPECT_RATIOS: List[str] = [
    "21:9", "16:9", "4:3", "3:2",  # Landscape
    "1:1",                         # Square
    "9:16", "3:4", "2:3",         # Portrait
    # "5:4", "4:5"                   # Flexible
]

def get_aspect_ratio_kb(generation_id: int) -> InlineKeyboardMarkup:
    """
    Creates a keyboard for selecting a new aspect ratio for reframing.

    Args:
        generation_id: The ID of the source generation to be reframed.

    Returns:
        An inline keyboard with aspect ratio options.
    """
    buttons = [
        InlineKeyboardButton(
            text=ratio,
            callback_data=SelectAspectRatioCallback(
                generation_id=generation_id, ratio=ratio
            ).pack(),
        )
        for ratio in SUPPORTED_ASPECT_RATIOS
    ]

    # Arrange buttons in rows of 4 for a clean layout
    layout = list(chunks(buttons, 4))
    
    return InlineKeyboardMarkup(inline_keyboard=layout)

# aiogram_bot_template/keyboards/inline/child_age.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.i18n import gettext as _
from .callbacks import (
    AgeSelectionCallback,
    GenderSelectionCallback,
    LikenessSelectionCallback,
)


def age_selection_kb() -> InlineKeyboardMarkup:
    """Creates a keyboard for child age group selection with emojis."""
    buttons = [
        [
            InlineKeyboardButton(
                text=_("👶 Baby (0-2 years)"),
                callback_data=AgeSelectionCallback(age_group="baby").pack(),
            )
        ],
        [
            InlineKeyboardButton(
                text=_("🧒 Child (5-10 years)"),
                callback_data=AgeSelectionCallback(age_group="child").pack(),
            )
        ],
        [
            InlineKeyboardButton(
                text=_("🧑 Teenager (13-18 years)"),
                callback_data=AgeSelectionCallback(age_group="teen").pack(),
            )
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def gender_selection_kb() -> InlineKeyboardMarkup:
    """Creates a keyboard for child gender selection with emojis."""
    buttons = [
        [
            InlineKeyboardButton(
                text=_("👦 Boy"),
                callback_data=GenderSelectionCallback(gender="boy").pack(),
            ),
            InlineKeyboardButton(
                text=_("👧 Girl"),
                callback_data=GenderSelectionCallback(gender="girl").pack(),
            ),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def likeness_selection_kb() -> InlineKeyboardMarkup:
    """Creates a keyboard for parent likeness selection with emojis."""
    buttons = [
        [
            InlineKeyboardButton(
                text=_("👨 Father"),
                callback_data=LikenessSelectionCallback(resemble="father").pack(),
            ),
            InlineKeyboardButton(
                text=_("👩 Mother"),
                callback_data=LikenessSelectionCallback(resemble="mother").pack(),
            ),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

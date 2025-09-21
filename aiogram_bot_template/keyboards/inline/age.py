# aiogram_bot_template/keyboards/inline/age.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.i18n import gettext as _
from .callbacks import ChildAgeCallback
from aiogram_bot_template.data.constants import ChildAge

def age_kb() -> InlineKeyboardMarkup:
    """Creates a keyboard for selecting a child's age category."""
    buttons = [
        [
            InlineKeyboardButton(
                text=_("Baby (0-2 years) 🍼"),
                callback_data=ChildAgeCallback(age=ChildAge.INFANT.value).pack(),
            ),
        ],
        [
            InlineKeyboardButton(
                text=_("Child (5-8 years) 🧒"),
                callback_data=ChildAgeCallback(age=ChildAge.CHILD.value).pack(),
            ),
        ],
        [
            InlineKeyboardButton(
                text=_("Teen (13-16 years) 🧑"),
                callback_data=ChildAgeCallback(age=ChildAge.TEEN.value).pack(),
            )
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
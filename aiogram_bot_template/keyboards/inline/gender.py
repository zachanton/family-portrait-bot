# aiogram_bot_template/keyboards/inline/gender.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.i18n import gettext as _
from .callbacks import ChildGenderCallback
from aiogram_bot_template.data.constants import ChildGender

def gender_kb() -> InlineKeyboardMarkup:
    """Creates a keyboard for selecting a child's gender."""
    buttons = [
        [
            InlineKeyboardButton(
                text=_("Boy 👦"),
                callback_data=ChildGenderCallback(gender=ChildGender.BOY.value).pack(),
            ),
            InlineKeyboardButton(
                text=_("Girl 👧"),
                callback_data=ChildGenderCallback(gender=ChildGender.GIRL.value).pack(),
            ),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
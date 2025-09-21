# aiogram_bot_template/keyboards/inline/resemblance.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.i18n import gettext as _
from .callbacks import ChildResemblanceCallback
from aiogram_bot_template.data.constants import ChildResemblance

def resemblance_kb() -> InlineKeyboardMarkup:
    """Creates a keyboard for selecting whom the child should resemble more."""
    buttons = [
        [
            InlineKeyboardButton(
                text=_("Mom 👩"),
                callback_data=ChildResemblanceCallback(resemblance=ChildResemblance.MOM.value).pack(),
            ),
            InlineKeyboardButton(
                text=_("Dad 👨"),
                callback_data=ChildResemblanceCallback(resemblance=ChildResemblance.DAD.value).pack(),
            ),
        ],
        [
            InlineKeyboardButton(
                text=_("Both 🧑‍🤝‍🧑"),
                callback_data=ChildResemblanceCallback(resemblance=ChildResemblance.BOTH.value).pack(),
            )
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
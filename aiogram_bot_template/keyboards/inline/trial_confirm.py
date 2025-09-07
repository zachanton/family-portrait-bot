# aiogram_bot_template/keyboards/inline/trial_confirm.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.i18n import gettext as _

def trial_confirm_kb() -> InlineKeyboardMarkup:
    """
    Creates a keyboard for the user to confirm the terms of the free trial.
    """
    buttons = [
        [
            InlineKeyboardButton(
                text=_("✅ I Agree & Start Free Trial"),
                callback_data="trial_confirm:yes"
            )
        ],
        [
            InlineKeyboardButton(
                text=_("⬅️ No, Show Paid Options"),
                callback_data="trial_confirm:no"
            )
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
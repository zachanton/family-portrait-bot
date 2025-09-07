# aiogram_bot_template/keyboards/inline/confirm.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.i18n import gettext as _
from .callbacks import ReturnToMainMenu


def create_yes_no_kb(yes_callback: str, no_callback: str) -> InlineKeyboardMarkup:
    """
    Creates an inline keyboard with Yes/No buttons and custom callback data.

    Returns:
        InlineKeyboardMarkup: The keyboard.
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=_("✅ Yes"), callback_data=yes_callback),
                InlineKeyboardButton(text=_("❌ No"), callback_data=no_callback),
            ],
        ],
    )


def create_user_prompt_confirm_kb(continue_key: str, request_id: int) -> InlineKeyboardMarkup:
    """
    Creates a confirmation keyboard for user-entered text prompts.
    Includes Yes, No, and a Back button to the main next_step menu.
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=_("✅ Yes"), callback_data="user_prompt_yes"),
                InlineKeyboardButton(text=_("❌ No"), callback_data="user_prompt_no"),
            ],
            [
                InlineKeyboardButton(
                    text=_("⬅️ Back to Options"),
                    callback_data=ReturnToMainMenu(key=continue_key, request_id=request_id).pack(),
                )
            ]
        ]
    )

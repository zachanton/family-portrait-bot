# aiogram_bot_template/keyboards/inline/next_step.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.i18n import gettext as _
from .callbacks import RetryGenerationCallback

def get_next_step_keyboard(continue_key: str, request_id: int) -> InlineKeyboardMarkup:
    """
    Creates a keyboard for post-generation actions.
    """
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=_("🔁 Retry Variation"),
                callback_data=RetryGenerationCallback(request_id=request_id).pack()
            )
        ],
        [
            InlineKeyboardButton(
                text=_("🔄 Start a New Generation"),
                callback_data="start_new"
            )
        ],
    ])
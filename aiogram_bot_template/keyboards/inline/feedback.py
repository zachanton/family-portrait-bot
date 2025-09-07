# aiogram_bot_template/keyboards/inline/feedback.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.i18n import gettext as _
from .callbacks import FeedbackCallback


def feedback_kb(generation_id: int, request_id: int, continue_key: str) -> InlineKeyboardMarkup:
    """Creates a keyboard for providing feedback on a generation."""
    buttons = [
        [
            InlineKeyboardButton(
                text=_("👍 Like"),
                callback_data=FeedbackCallback(action="like", generation_id=generation_id, request_id=request_id, continue_key=continue_key).pack(),
            ),
            InlineKeyboardButton(
                text=_("👎 Dislike"),
                callback_data=FeedbackCallback(action="dislike", generation_id=generation_id, request_id=request_id, continue_key=continue_key).pack(),
            ),
        ],
        [
            InlineKeyboardButton(
                text=_("➡️ Continue"),
                callback_data=FeedbackCallback(action="skip", generation_id=generation_id, request_id=request_id, continue_key=continue_key).pack(),
            )
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

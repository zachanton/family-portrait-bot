# aiogram_bot_template/keyboards/inline/__init__.py
from .callbacks import LanguageCallback, FeedbackCallback
from .feedback import feedback_kb
from .language import language_kb
from .next_step import get_next_step_keyboard
from .quality import quality_kb

__all__ = [
    "LanguageCallback",
    "FeedbackCallback",
    "feedback_kb",
    "language_kb",
    "get_next_step_keyboard",
    "quality_kb",
]
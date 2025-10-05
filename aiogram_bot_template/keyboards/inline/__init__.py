# aiogram_bot_template/keyboards/inline/__init__.py
from .callbacks import LanguageCallback
from .language import language_kb
from .next_step import get_next_step_keyboard
from .quality import quality_kb

__all__ = [
    "LanguageCallback",
    "language_kb",
    "get_next_step_keyboard",
    "quality_kb",
]
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.i18n import I18n

from .callbacks import LanguageCallback

# For aesthetics, you can set the language names in their native language
LANGUAGE_NAMES = {
    "en": "🇬🇧 English",
    "ru": "🇷🇺 Русский",
    "es": "🇪🇸 Español",
}


def language_kb(i18n: I18n) -> InlineKeyboardMarkup:
    """
    Creates a keyboard for language selection.

    Returns:
        An InlineKeyboardMarkup with language buttons.
    """
    buttons = [
        [
            InlineKeyboardButton(
                text=LANGUAGE_NAMES.get(code, code),
                callback_data=LanguageCallback(action="select", code=code).pack(),
            )
        ]
        for code in i18n.available_locales
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

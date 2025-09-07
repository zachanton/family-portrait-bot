# aiogram_bot_template/keyboards/inline/language.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.i18n import I18n

from .callbacks import LanguageCallback

# Для красоты можно указать названия языков на них самих
LANGUAGE_NAMES = {
    "en": "🇬🇧 English",
    "ru": "🇷🇺 Русский",
    "es": "🇪🇸 Español",
}


def language_kb(i18n: I18n) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для выбора языка.
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
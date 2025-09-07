# aiogram_bot_template/data/texts/__init__.py
from . import en, ru, es
from .dto import LocaleTexts

ALL_TEXTS = {
    "en": en.texts,
    "ru": ru.texts,
    "es": es.texts,
}

DEFAULT_LANG = "en"

def get_texts(locale: str) -> LocaleTexts:
    return ALL_TEXTS.get(locale, ALL_TEXTS[DEFAULT_LANG])
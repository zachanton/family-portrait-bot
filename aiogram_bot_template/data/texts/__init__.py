# aiogram_bot_template/data/texts/__init__.py
from .en import texts as en_texts
from .ru import texts as ru_texts
from .es import texts as es_texts
from .dto import LocaleTexts

ALL_TEXTS: dict[str, LocaleTexts] = {
    "en": en_texts,
    "ru": ru_texts,
    "es": es_texts,
}

DEFAULT_LOCALE = "en"


def get_texts(locale: str) -> LocaleTexts:
    """
    Retrieves the text object for a given locale, falling back to the default.
    """
    return ALL_TEXTS.get(locale, ALL_TEXTS[DEFAULT_LOCALE])
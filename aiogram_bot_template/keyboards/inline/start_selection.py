# aiogram_bot_template/keyboards/inline/start_selection.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.i18n import gettext as _
from .callbacks import StartScenarioCallback
from aiogram_bot_template.data.constants import GenerationType

def start_scenario_kb() -> InlineKeyboardMarkup:
    """
    Creates a keyboard for selecting the initial generation scenario.
    """
    buttons = [
        [
            InlineKeyboardButton(
                text=_("👶 Generate Future Child"),
                callback_data=StartScenarioCallback(
                    type=GenerationType.CHILD_GENERATION.value
                ).pack(),
            )
        ],
        [
            InlineKeyboardButton(
                text=_("💑 Create Couple Portrait"),
                callback_data=StartScenarioCallback(
                    type=GenerationType.PAIR_PHOTO.value
                ).pack(),
            )
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
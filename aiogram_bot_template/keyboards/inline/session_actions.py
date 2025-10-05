# aiogram_bot_template/keyboards/inline/session_actions.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.i18n import gettext as _
from .callbacks import SessionActionCallback
from aiogram_bot_template.data.constants import GenerationType
from typing import Set

def session_actions_kb(generated_types: Set[str]) -> InlineKeyboardMarkup:
    """
    Creates a keyboard for post-generation actions within a session.
    The labels change based on what has already been generated.

    Args:
        generated_types: A set of generation types already completed in this session.

    Returns:
        An inline keyboard with session actions.
    """
    buttons = []

    # --- Child Generation Button ---
    if GenerationType.CHILD_GENERATION.value in generated_types:
        child_text = _("👶 Generate Another Child")
    else:
        child_text = _("👶 Generate Future Child")
    buttons.append(
        [
            InlineKeyboardButton(
                text=child_text,
                callback_data=SessionActionCallback(
                    action_type=GenerationType.CHILD_GENERATION.value
                ).pack(),
            )
        ]
    )

    # --- Pair Photo Button ---
    if GenerationType.PAIR_PHOTO.value in generated_types:
        pair_text = _("💑 Create Another Couple Portrait")
    else:
        pair_text = _("💑 Create Couple Portrait")
    buttons.append(
        [
            InlineKeyboardButton(
                text=pair_text,
                callback_data=SessionActionCallback(
                    action_type=GenerationType.PAIR_PHOTO.value
                ).pack(),
            )
        ]
    )

    # --- Start New Session Button ---
    buttons.append(
        [
            InlineKeyboardButton(
                text=_("🔄 Start a New Session"), callback_data="start_new"
            )
        ]
    )
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)
# aiogram_bot_template/keyboards/inline/edit_prompts.py
from typing import Any

import structlog
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.i18n import gettext as _

from ...data.constants import GenerationType
from ...dto.facial_features import ImageDescription
from ...dto.prompt_suggestions import (
    ALL_PROMPT_SUGGESTIONS, EDIT_MENU_STRUCTURE, GROUP_PHOTO_EDIT_MENU_STRUCTURE
)
from ...services.suggestion_engine import SuggestionEngine
from .callbacks import EditMenuCallback, ReturnToMainMenu

logger = structlog.get_logger(__name__)


def create_edit_menu_kb(
    back_continue_key: str,
    back_request_id: int,
    child_description: ImageDescription | None,
    parent_descriptions: dict[str, Any] | None,
    generation_type: GenerationType,
    path: str | None = None,
) -> InlineKeyboardMarkup:
    """
    Dynamically and reliably creates a multi-level keyboard for image editing.
    This version uses a clean, declarative structure and selects the appropriate
    menu based on the type of image being edited.
    """
    buttons: list[InlineKeyboardButton] = []
    engine = SuggestionEngine(
        child_description, parent_descriptions
    )

    # Choose the menu structure based on the generation type
    base_menu_structure = (
        GROUP_PHOTO_EDIT_MENU_STRUCTURE
        if generation_type == GenerationType.GROUP_PHOTO
        else EDIT_MENU_STRUCTURE
    )
    
    current_node = base_menu_structure
    if path:
        for key in path.split("|"):
            current_node = current_node.get("subcategories", {}).get(key, {})

    log = logger.bind(path=path or "root", type=generation_type.value)
    log.info("Creating edit menu keyboard")

    if dynamic_key := current_node.get("dynamic_key"):
        suggestion_keys = engine.generate_dynamic_suggestions(dynamic_key)

        log.info("Generated dynamic suggestion keys", keys=suggestion_keys, dynamic_key=dynamic_key)

        for s_key in suggestion_keys:
            s = ALL_PROMPT_SUGGESTIONS.get(s_key)
            log.info("Checking suggestion key", key=s_key, found=s is not None)
            if s:
                buttons.append(
                    InlineKeyboardButton(
                        text=f"{s.emoji} {_(s.text)}",
                        callback_data=f"prompt_suggestion:{s_key}",
                    )
                )

    elif static_keys := current_node.get("suggestions"):
        for s_key in static_keys:
            if s := ALL_PROMPT_SUGGESTIONS.get(s_key):
                buttons.append(
                    InlineKeyboardButton(
                        text=f"{s.emoji} {_(s.text)}",
                        callback_data=f"prompt_suggestion:{s_key}",
                    )
                )

    if subcategories := current_node.get("subcategories"):
        for key, data in subcategories.items():
            new_path = f"{path}|{key}" if path else key
            buttons.append(
                InlineKeyboardButton(
                    text=f"{data['emoji']} {_(data['title'])}",
                    callback_data=EditMenuCallback(path=new_path).pack(),
                )
            )

    if not path:
        buttons.append(
            InlineKeyboardButton(
                text=_("📝 Enter a Custom Prompt"),
                callback_data="prompt_suggestion:custom",
            )
        )

    buttons.append(
        InlineKeyboardButton(
            text=_("⬅️ Back to Options"),
            callback_data=ReturnToMainMenu(
                key=back_continue_key, request_id=back_request_id
            ).pack(),
        )
    )

    layout = [[btn] for btn in buttons]

    num_common_buttons = 2 if not path else 1
    if len(layout) == num_common_buttons:
        # Avoid showing an empty menu for group photos
        if base_menu_structure != GROUP_PHOTO_EDIT_MENU_STRUCTURE:
            no_options_button = InlineKeyboardButton(
                text=_("No personalized suggestions available"), callback_data="do_nothing"
            )
            layout.insert(0, [no_options_button])

    log.info("Final number of buttons created", count=len(buttons))
    return InlineKeyboardMarkup(inline_keyboard=layout)
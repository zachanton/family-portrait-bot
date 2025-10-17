# aiogram_bot_template/keyboards/inline/family_selection.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.i18n import gettext as _
from .callbacks import ContinueWithFamilyPhotoCallback, EditImageCallback, ReframeImageCallback


def continue_with_family_photo_kb(
    generation_id: int, request_id: int
) -> InlineKeyboardMarkup:
    """
    Creates a keyboard with a 'Continue with this family portrait' button.

    Args:
        generation_id: The ID of the specific generation this button is attached to.
        request_id: The ID of the parent generation request.

    Returns:
        An inline keyboard.
    """
    buttons = [
        [
            InlineKeyboardButton(
                text=_("❤️ I choose this one!"),
                callback_data=ContinueWithFamilyPhotoCallback(
                    generation_id=generation_id,
                    request_id=request_id,
                ).pack(),
            )
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def post_family_photo_selection_kb(generation_id: int) -> InlineKeyboardMarkup:
    """
    Creates a keyboard for the final action after selecting a family portrait.
    The 'Start a New Generation' button is replaced with 'Return to Menu'.

    Args:
        generation_id: The ID of the selected generation to enable editing.

    Returns:
        An inline keyboard with the next action step.
    """
    buttons = [
        [
            InlineKeyboardButton(
                text=_("✏️ Edit This Portrait"),
                callback_data=EditImageCallback(generation_id=generation_id).pack(),
            ),
            # --- NEW BUTTON ---
            InlineKeyboardButton(
                text=_("🖼️ Reframe"),
                callback_data=ReframeImageCallback(generation_id=generation_id).pack(),
            )
        ],
        [
            InlineKeyboardButton(
                text=_("↩️ Return to Menu"), callback_data="return_to_session_menu"
            )
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

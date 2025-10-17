# aiogram_bot_template/keyboards/inline/child_selection.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.i18n import gettext as _
from .callbacks import (
    ContinueWithImageCallback,
    CreateFamilyPhotoCallback,
    RetryGenerationCallback,
    EditImageCallback,
    ReframeImageCallback,
)


def continue_with_image_kb(
    generation_id: int, request_id: int
) -> InlineKeyboardMarkup:
    """
    Creates a keyboard with a 'Continue with this image' button.

    Args:
        generation_id: The ID of the specific generation this button is attached to.
        request_id: The ID of the parent generation request.

    Returns:
        An inline keyboard.
    """
    buttons = [
        [
            InlineKeyboardButton(
                text=_("😍 Select This Portrait"),
                callback_data=ContinueWithImageCallback(
                    generation_id=generation_id,
                    request_id=request_id,
                ).pack(),
            )
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def post_child_selection_kb(
    generation_id: int, request_id: int
) -> InlineKeyboardMarkup:
    """
    Creates a keyboard for actions after selecting a child image.
    The 'Start a New Generation' button is replaced with 'Return to Menu'.

    Args:
        generation_id: The ID of the selected generation.
        request_id: The ID of the parent generation request.

    Returns:
        An inline keyboard with next action steps.
    """
    buttons = [
        [
            InlineKeyboardButton(
                text=_("👨‍👩‍👧 Create Family Photo"),
                callback_data=CreateFamilyPhotoCallback(
                    child_generation_id=generation_id, parent_request_id=request_id
                ).pack(),
            ),
        ],
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

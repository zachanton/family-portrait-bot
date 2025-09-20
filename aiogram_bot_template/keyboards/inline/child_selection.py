# aiogram_bot_template/keyboards/inline/child_selection.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.i18n import gettext as _
from .callbacks import (
    ContinueWithImageCallback,
    CreateFamilyPhotoCallback,
    RetryGenerationCallback,
)


def continue_with_image_kb(
    generation_id: int, request_id: int, next_step_message_id: int
) -> InlineKeyboardMarkup:
    """
    Creates a keyboard with a 'Continue with this image' button.

    Args:
        generation_id: The ID of the specific generation this button is attached to.
        request_id: The ID of the parent generation request.
        next_step_message_id: The ID of the final 'Try Again' message to be deleted on click.

    Returns:
        An inline keyboard.
    """
    buttons = [
        [
            InlineKeyboardButton(
                text=_("😍 Continue with this child"),
                callback_data=ContinueWithImageCallback(
                    generation_id=generation_id,
                    request_id=request_id,
                    next_step_message_id=next_step_message_id,
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
    Now includes a 'Try again' button.

    Args:
        generation_id: The ID of the selected generation.
        request_id: The ID of the parent generation request.

    Returns:
        An inline keyboard with next action steps.
    """
    buttons = [
        [
            InlineKeyboardButton(
                text=_("👨‍👩‍👧 Create a group photo with this child"),
                callback_data=CreateFamilyPhotoCallback(
                    child_generation_id=generation_id, parent_request_id=request_id
                ).pack(),
            ),
        ],
        [
            InlineKeyboardButton(
                text=_("🔁 Try again"),
                callback_data=RetryGenerationCallback(request_id=request_id).pack(),
            )
        ],
        [
            InlineKeyboardButton(
                text=_("🔄 Start a New Generation"), callback_data="start_new"
            )
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
# aiogram_bot_template/handlers/edit_handler.py
import asyncio  # <-- NEW IMPORT
import asyncpg
import structlog
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram.filters import StateFilter
from aiogram.utils.i18n import gettext as _
from contextlib import suppress # <-- NEW IMPORT
from aiogram.exceptions import TelegramBadRequest # <-- NEW IMPORT

from aiogram_bot_template.data.constants import GenerationType
from aiogram_bot_template.states.user import Generation
from aiogram_bot_template.utils import moderation
from aiogram_bot_template.utils.status_manager import StatusMessageManager # <-- NEW IMPORT
from aiogram_bot_template.keyboards.inline.quality import quality_kb
from aiogram_bot_template.db.db_api.storages import PostgresConnection
from aiogram_bot_template.db.repo import users as users_repo
from aiogram_bot_template.data.settings import settings


router = Router(name="edit-handler")


@router.message(StateFilter(Generation.waiting_for_edit_prompt), F.text)
async def process_edit_prompt(
    message: Message,
    state: FSMContext,
    db_pool: asyncpg.Pool,
    business_logger: structlog.typing.FilteringBoundLogger,
) -> None:
    """
    Handles the user's text prompt for image editing, moderates it,
    and then proceeds to quality/payment selection.
    """
    prompt = message.text
    if not prompt:
        await message.answer(_("Please provide a description of the changes you'd like to make."))
        return

    # --- UPDATED LOGIC: Use StatusMessageManager for better UX ---
    status_msg = await message.answer(_("Checking your request... 📝"))
    status_manager = StatusMessageManager(
        bot=message.bot,
        chat_id=message.chat.id,
        message_id=status_msg.message_id,
        min_duration=1.0  # A shorter duration is fine for this quick check
    )
    
    # Run moderation check
    is_safe = await moderation.is_safe_prompt(prompt)
    
    if not is_safe:
        await status_manager.update(
            _("This prompt seems to violate our safety policy. 🧐 Please try a different one.")
        )
        # We leave the message on screen for the user to read it.
        # No need to delete it immediately.
        return

    # If safe, proceed to the next step
    await status_manager.update(_("Prompt accepted! Preparing options... ✅"))
    # The message will be deleted by the quality selection handler later
    
    # Save the safe prompt and move to quality selection
    await state.update_data(
        user_prompt=prompt,
        generation_type=GenerationType.IMAGE_EDIT.value,
    )

    db = PostgresConnection(db_pool, logger=business_logger)
    user_id = message.from_user.id
    
    is_in_whitelist = user_id in settings.free_trial_whitelist
    has_used_queue = True  # No live queue for edits

    # Delete the status message before showing the keyboard
    with suppress(TelegramBadRequest):
        await status_msg.delete()

    await state.set_state(Generation.waiting_for_edit_quality)
    await message.answer(
        _("✨ Now, please choose a package for this edit:"),
        reply_markup=quality_kb(
            generation_type=GenerationType.IMAGE_EDIT,
            is_trial_available=is_in_whitelist,
            is_live_queue_available=not has_used_queue
        ),
    )
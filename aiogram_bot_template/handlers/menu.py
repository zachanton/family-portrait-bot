# aiogram_bot_template/handlers/menu.py
import asyncpg
import structlog
from aiogram import Bot, Router
from aiogram.filters import Command, StateFilter, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from aiogram.utils.i18n import gettext as _
from contextlib import suppress
from aiogram.exceptions import TelegramBadRequest

from aiogram_bot_template.data.constants import GenerationType
from aiogram_bot_template.db.db_api.storages import PostgresConnection
from aiogram_bot_template.db.repo.users import add_or_update_user
from aiogram_bot_template.keyboards.inline.callbacks import StartScenarioCallback
from aiogram_bot_template.keyboards.inline.start_selection import start_scenario_kb
from aiogram_bot_template.states.user import Generation

router = Router(name="menu-handlers")


async def _cleanup_selection_messages(bot: Bot, chat_id: int, state: FSMContext) -> None:
    """
    Performs a full cleanup of the interactive selection interface.
    It removes keyboards from all generated photos and deletes the separate
    "action prompt" message (e.g., "You've selected this child...").
    This is intended to be called when the user's session is terminated or moves to a new stage.
    """
    if not state:
        return
        
    user_data = await state.get_data()
    photo_message_ids = user_data.get("photo_message_ids", [])
    next_step_message_id = user_data.get("next_step_message_id")

    # Delete the separate action prompt message
    if next_step_message_id:
        with suppress(TelegramBadRequest):
            await bot.delete_message(chat_id=chat_id, message_id=next_step_message_id)

    # Remove keyboards from all generated photos to make them non-interactive
    if photo_message_ids:
        for msg_id in photo_message_ids:
            with suppress(TelegramBadRequest):
                await bot.edit_message_reply_markup(chat_id=chat_id, message_id=msg_id, reply_markup=None)


async def send_welcome_message(msg: Message, state: FSMContext, is_restart: bool = False):
    """Sends the welcome/restart message and prompts for scenario selection."""
    await _cleanup_selection_messages(msg.bot, msg.chat.id, state)
    
    await state.clear()
    await state.set_state(Generation.choosing_scenario)

    if is_restart:
        text = _(
            "Let's start over! What would you like to create?"
        )
    else:
        text = _(
            "<b>Welcome! I can create a beautiful AI-powered portrait.</b>\n\n"
            "What would you like to do?"
        )
    await msg.answer(text, reply_markup=start_scenario_kb())


@router.message(Command("start", "menu"), StateFilter("*"))
async def start_flow(
    msg: Message,
    state: FSMContext,
    business_logger: structlog.typing.FilteringBoundLogger,
    db_pool: asyncpg.Pool,
    command: CommandObject | None = None,
) -> None:
    """Handles /start and /menu, initiating the scenario selection flow."""
    db = PostgresConnection(db_pool, logger=business_logger)
    if msg.from_user:
        referral_source = command.args if command and command.args else None
        
        await add_or_update_user(
            db=db,
            user_id=msg.from_user.id,
            username=msg.from_user.username,
            first_name=msg.from_user.first_name,
            language_code=msg.from_user.language_code,
            referral_source=referral_source,
        )
    await send_welcome_message(msg, state)


@router.message(Command("cancel"), StateFilter("*"))
async def cancel_flow(msg: Message, state: FSMContext) -> None:
    """Handles /cancel command."""
    await send_welcome_message(msg, state, is_restart=True)


@router.callback_query(StartScenarioCallback.filter(), StateFilter(Generation.choosing_scenario))
async def process_scenario_selection(
    cb: CallbackQuery,
    callback_data: StartScenarioCallback,
    state: FSMContext,
) -> None:
    """
    Handles the user's choice of generation type and transitions to the next step.
    """
    await cb.answer()
    
    await state.set_state(Generation.collecting_photos)
    # Store the selected generation type to guide the rest of the flow
    await state.update_data(
        generation_type=callback_data.type,
        photos_collected=[],
        album_cache={}
    )
    
    if callback_data.type == GenerationType.CHILD_GENERATION.value:
        text = _("Great! Let's imagine your future child.\n\n"
                 "To begin, please send one or more photos of the Mother.")
    elif callback_data.type == GenerationType.PAIR_PHOTO.value:
        text = _("Excellent! Let's create a stunning couple portrait.\n\n"
                 "Please start by sending one or more photos of the first person.")
    else:
        text = _("Sorry, something went wrong. Please /start again.")
        await state.clear()

    await cb.message.edit_text(text, reply_markup=None)
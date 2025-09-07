# aiogram_bot_template/handlers/menu.py
import asyncpg
import structlog
from aiogram import Bot, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram.utils.i18n import gettext as _

from aiogram_bot_template.db.db_api.storages import PostgresConnection
from aiogram_bot_template.db.repo.users import add_or_update_user
from aiogram_bot_template.states.user import Generation

router = Router(name="menu-handlers")

async def send_welcome_message(msg: Message, state: FSMContext, is_restart: bool = False):
    """Sends the welcome/restart message and sets the initial state."""
    await state.clear()
    await state.set_state(Generation.collecting_photos)
    await state.update_data(photos_collected=[])

    if is_restart:
        text = _("Okay, let's start over. Please send the first photo.")
    else:
        text = _(
            "<b>Welcome! I can create a beautiful group portrait for two people.</b>\n\n"
            "To begin, please send the first person's photo."
        )
    await msg.answer(text)

@router.message(Command("start", "menu"), StateFilter("*"))
async def start_flow(
    msg: Message,
    state: FSMContext,
    business_logger: structlog.typing.FilteringBoundLogger,
    db_pool: asyncpg.Pool,
) -> None:
    """Handles /start and /menu, initiating the flow."""
    db = PostgresConnection(db_pool, logger=business_logger)
    if msg.from_user:
        await add_or_update_user(
            db=db,
            user_id=msg.from_user.id,
            username=msg.from_user.username,
            first_name=msg.from_user.first_name,
            language_code=msg.from_user.language_code,
        )
    await send_welcome_message(msg, state)

@router.message(Command("cancel"), StateFilter("*"))
async def cancel_flow(msg: Message, state: FSMContext) -> None:
    """Handles /cancel command."""
    await send_welcome_message(msg, state, is_restart=True)
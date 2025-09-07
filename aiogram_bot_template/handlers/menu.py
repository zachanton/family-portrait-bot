# aiogram_bot_template/handlers/menu.py
import asyncpg
import structlog
from aiogram import Bot, Router
from aiogram.filters import Command, CommandObject, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram.utils.i18n import gettext as _
from contextlib import suppress
from aiogram.exceptions import TelegramBadRequest

from aiogram_bot_template.db.db_api.storages import PostgresConnection
from aiogram_bot_template.db.repo import generations as generations_repo
from aiogram_bot_template.db.repo.users import add_or_update_user
from aiogram_bot_template.states.user import Generation
from aiogram_bot_template.data import constants
from aiogram_bot_template.data import message_provider

from aiogram_bot_template.data.constants import GenerationType

router = Router(name="menu-handlers")


async def _send_welcome_message_and_set_state(
    msg: Message, state: FSMContext, *, is_restart: bool = False
) -> None:
    """
    A helper function to send a welcome/restart message and reset the state.
    """
    # Initialize or reset the state for the main flow
    await state.update_data(
        generation_type=GenerationType.CHILD_GENERATION,
        photos_needed=2,
        photos_collected=[],
    )

    if is_restart:
        text_to_send = message_provider.get_restart_message()
    else:
        text_to_send = message_provider.get_start_message()

    await msg.answer(text_to_send)

    await state.set_state(Generation.collecting_inputs)


async def _cancel_pending_request(
    state: FSMContext,
    bot: Bot,
    db: PostgresConnection,
    chat_id: int,
    business_logger: structlog.typing.FilteringBoundLogger,
):
    """Checks for and cancels an active request, especially in the payment state."""
    current_state = await state.get_state()
    if current_state != Generation.waiting_for_payment.state:
        return

    data = await state.get_data()
    request_id = data.get("request_id")
    invoice_message_id = data.get("invoice_message_id")

    if request_id:
        await generations_repo.update_generation_request_status(db, request_id, "cancelled_by_user")
        business_logger.info("Request cancelled by user action", request_id=request_id)

    if invoice_message_id:
        with suppress(TelegramBadRequest):
            # We try to delete the old invoice to avoid confusion
            await bot.delete_message(chat_id, invoice_message_id)

async def _deactivate_all_previous_generations(
    user_id: int,
    bot: Bot,
    db: PostgresConnection,
    state: FSMContext,
    business_logger: structlog.typing.FilteringBoundLogger,
):
    """
    Finds all previous generation messages with "Return to..." buttons for a user
    and removes their keyboards, effectively deactivating them.
    It excludes the currently active generation from deactivation.
    Also nullifies the message IDs in the database to prevent re-processing.
    """
    user_data = await state.get_data()
    active_generation_id = user_data.get("active_generation_id")

    sql_get_messages = """
        SELECT g.id, g.result_message_id
        FROM generations g
        JOIN generation_requests gr ON g.request_id = gr.id
        WHERE gr.user_id = $1 
          AND g.result_message_id IS NOT NULL
          AND ($2::int IS NULL OR g.id != $2::int); -- Exclude active generation
    """
    generations_to_deactivate = await db.fetch(sql_get_messages, (user_id, active_generation_id))
    
    if not generations_to_deactivate.data:
        return

    deactivated_count = 0
    generation_ids_to_update = []

    for record in generations_to_deactivate.data:
        message_id = record.get("result_message_id")
        generation_id = record.get("id")
        if not message_id or not generation_id:
            continue

        with suppress(TelegramBadRequest):
            await bot.edit_message_reply_markup(
                chat_id=user_id,
                message_id=message_id,
                reply_markup=None
            )
            generation_ids_to_update.append(generation_id)
            deactivated_count += 1
    
    if generation_ids_to_update:
        sql_update_db = """
            UPDATE generations
            SET result_message_id = NULL, control_message_id = NULL
            WHERE id = ANY($1::int[]);
        """
        await db.execute(sql_update_db, (generation_ids_to_update,))
    
    if deactivated_count > 0:
        business_logger.info(f"Deactivated {deactivated_count} previous generation buttons for user.")


@router.message(Command("start", "menu"), StateFilter("*"))
async def start_flow(
    msg: Message,
    state: FSMContext,
    bot: Bot,
    business_logger: structlog.typing.FilteringBoundLogger,
    command: CommandObject | None = None,
    db_pool: asyncpg.Pool | None = None,
) -> None:
    """
    Handles /start and /menu, initiating the primary child generation flow.
    Serves as the main entry and reset point.
    """
    referral_source = None
    if db_pool and msg.from_user:
        db = PostgresConnection(db_pool, logger=business_logger, decode_json=True)

        await _cancel_pending_request(state, bot, db, msg.chat.id, business_logger)
        await _deactivate_all_previous_generations(msg.from_user.id, bot, db, state, business_logger)

        lang_code = msg.from_user.language_code

        referral_source = (
            command.args
            if command
            and command.args
            and len(command.args) <= constants.MAX_REFERRAL_CODE_LENGTH
            else None
        )

        await add_or_update_user(
            db=db,
            user_id=msg.from_user.id,
            username=msg.from_user.username,
            first_name=msg.from_user.first_name,
            language_code=lang_code,
            referral_source=referral_source,
        )
        business_logger.info("User added or updated in DB", user_id=msg.from_user.id)
    else:
        business_logger.info(
            "DB is not connected or user is missing, skipping user save."
        )

    await state.clear()
    if referral_source:
        await state.update_data(referral_source=referral_source)
    await _send_welcome_message_and_set_state(msg, state)


@router.message(Command("cancel"), StateFilter("*"))
async def cancel_flow(
    msg: Message,
    state: FSMContext,
    bot: Bot,
    db_pool: asyncpg.Pool,
    business_logger: structlog.typing.FilteringBoundLogger,
) -> None:
    """
    Handles /cancel command, allowing the user to restart the process from any state.
    """
    db = PostgresConnection(db_pool, logger=business_logger)
    await _cancel_pending_request(state, bot, db, msg.chat.id, business_logger)
    if msg.from_user:
        await _deactivate_all_previous_generations(msg.from_user.id, bot, db, state, business_logger)

    await state.clear()
    # COMBINED MESSAGE: Acknowledge cancellation and prompt for the next action in one message.
    await msg.answer(_("Your previous action has been cancelled. Let's start over!"))
    await _send_welcome_message_and_set_state(msg, state, is_restart=True)
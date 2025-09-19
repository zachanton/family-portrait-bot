# aiogram_bot_template/handlers/feedback_handler.py
import asyncio
import asyncpg
import structlog
from aiogram import Bot, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from aiogram.utils.i18n import gettext as _
from contextlib import suppress
from aiogram.exceptions import TelegramBadRequest

from aiogram_bot_template.data.settings import settings
from aiogram_bot_template.db.db_api.storages import PostgresConnection
from aiogram_bot_template.db.repo import feedback as feedback_repo
from aiogram_bot_template.keyboards.inline.callbacks import FeedbackCallback
from aiogram_bot_template.keyboards.inline import next_step
from aiogram_bot_template.states.user import Generation

router = Router(name="feedback-handler")


async def _process_feedback_async(
    cb: CallbackQuery,
    callback_data: FeedbackCallback,
    bot: Bot,
    db_pool: asyncpg.Pool,
    business_logger: structlog.typing.FilteringBoundLogger,
    state: FSMContext,
) -> None:
    """Performs the actual feedback processing in the background."""
    db = PostgresConnection(db_pool, logger=business_logger)
    user = cb.from_user
    next_step_text = ""

    if callback_data.action in ["like", "dislike"]:
        await feedback_repo.add_feedback(
            db, user_id=user.id, generation_id=callback_data.generation_id, rating=callback_data.action
        )
        log = business_logger.bind(user_id=user.id, gen_id=callback_data.generation_id, action=callback_data.action)
        log.info("User feedback was saved to DB.")
        next_step_text = _("Thank you for your feedback! What would you like to do next?")
    else:  # Handles the "skip" action (our "Continue" button)
        next_step_text = _("What would you like to do next?")

    reply_markup = next_step.get_next_step_keyboard(
        continue_key=callback_data.continue_key, request_id=callback_data.request_id
    )

    if cb.message:
        # --- FIX: The robust way to handle this ---
        # 1. First, remove the keyboard from the photo message to show it's been handled.
        with suppress(TelegramBadRequest):
            await cb.message.edit_reply_markup(reply_markup=None)
        
        # 2. Then, send a NEW message with the text and the next set of buttons.
        # This completely avoids the 'edit_message_text' error.
        await cb.message.answer(text=next_step_text, reply_markup=reply_markup)

    await state.set_state(Generation.waiting_for_next_action)


@router.callback_query(FeedbackCallback.filter())
async def handle_feedback(
    cb: CallbackQuery,
    callback_data: FeedbackCallback,
    bot: Bot,
    db_pool: asyncpg.Pool,
    business_logger: structlog.typing.FilteringBoundLogger,
    state: FSMContext,
) -> None:
    """
    Instantly acknowledges the user's feedback and delegates the processing
    to a background task.
    """
    with suppress(TelegramBadRequest):
        await cb.answer()

    asyncio.create_task(
        _process_feedback_async(cb, callback_data, bot, db_pool, business_logger, state)
    )
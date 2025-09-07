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
from aiogram_bot_template.data.constants import GenerationType, SessionContextType

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
    db = PostgresConnection(db_pool, logger=business_logger, decode_json=True)
    user = cb.from_user
    next_step_text = ""

    if callback_data.action in ["like", "dislike"]:
        await feedback_repo.add_feedback(
            db,
            user_id=user.id,
            generation_id=callback_data.generation_id,
            rating=callback_data.action,
        )

        log = business_logger.bind(
            user_id=user.id,
            gen_id=callback_data.generation_id,
            action=callback_data.action,
        )
        log.info("User feedback was saved to DB.")

        if settings.bot.log_chat_id:
            icon = "👍" if callback_data.action == "like" else "👎"
            user_info = f"@{user.username}" if user.username else f"ID: {user.id}"
            log_text = f"{icon} Feedback from {user_info} on generation #{callback_data.generation_id}."

            try:
                # Let's try to forward the photo message, not the control message
                user_data_for_fwd = await state.get_data()
                photo_message_id = user_data_for_fwd.get("active_photo_message_id")
                
                await bot.forward_message(
                    chat_id=settings.bot.log_chat_id,
                    from_chat_id=cb.message.chat.id,
                    message_id=photo_message_id if photo_message_id else cb.message.message_id,
                    disable_notification=True,
                )
                await bot.send_message(
                    chat_id=settings.bot.log_chat_id,
                    text=log_text,
                    disable_notification=True,
                )
            except Exception:
                log.exception("Failed to send feedback notification to log chat")

        next_step_text = _("Thank you for your feedback! What would you like to do next?")
    else:  # Handles the "skip" action (our "Continue" button)
        next_step_text = _("What would you like to do next?")

    user_data = await state.get_data()
    
    # Get the session context directly from the FSM state
    session_context_str = user_data.get("session_context", SessionContextType.CHILD_GENERATION.value)
    session_context = SessionContextType(session_context_str)

    reply_markup = next_step.get_next_step_keyboard(
        context=session_context,
        continue_key=callback_data.continue_key,
        request_id=callback_data.request_id,
    )

    # Check if the message is still accessible before editing
    if cb.message:
        with suppress(TelegramBadRequest):
            await cb.message.edit_text(text=next_step_text, reply_markup=reply_markup)

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

    # Schedule the heavy lifting to run in the background
    asyncio.create_task(
        _process_feedback_async(
            cb, callback_data, bot, db_pool, business_logger, state
        )
    )

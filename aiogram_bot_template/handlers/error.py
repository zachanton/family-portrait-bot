# aiogram_bot_template/handlers/error.py
import structlog
from aiogram import Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Update, ErrorEvent
from aiogram.utils.i18n import I18n, gettext as _
from contextlib import suppress

logger = structlog.get_logger(__name__)

router = Router(name="error-handler")


@router.errors()
async def global_error_handler(
    update: ErrorEvent,
    i18n: I18n,
) -> bool:
    """Handle all uncaught exceptions."""
    exception = update.exception
    actual_update: Update = update.update

    # Immediately acknowledge the callback to prevent timeout errors for the user
    if actual_update.callback_query:
        with suppress(TelegramBadRequest):
            await actual_update.callback_query.answer()

    user = getattr(actual_update, "from_user", None)
    locale = user.language_code if user and user.language_code in i18n.available_locales else i18n.default_locale

    with i18n.context(), i18n.use_locale(locale):
        if isinstance(exception, TelegramBadRequest):
            if "message to delete not found" in str(exception).lower():
                logger.warning("Tried to delete a message that was already deleted.")
                return True
            if "message is not modified" in str(exception).lower():
                logger.warning("Tried to edit a message with the same content.")
                return True

        update_details = f'{{"update_id": {actual_update.update_id}}}'
        try:
            update_details = actual_update.model_dump_json(exclude_none=True)
        except Exception as e:
            logger.warning("Could not serialize update object for logging.", error=str(e), update_id=actual_update.update_id)

        logger.error("An unhandled exception occurred", exc_info=exception, extra={"update": update_details})

        error_message = _(
            "😔 Oops! Something went wrong on our end. "
            "Our team has been notified.\n\nPlease try your request again in a few moments."
        )

        target_message = actual_update.callback_query.message if actual_update.callback_query else actual_update.message

        if target_message:
            with suppress(TelegramBadRequest):
                if target_message.photo or target_message.document:
                    await target_message.edit_caption(caption=error_message, reply_markup=None)
                else:
                    await target_message.edit_text(error_message, reply_markup=None)

    return True

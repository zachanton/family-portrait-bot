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
    """
    Handles all uncaught exceptions.
    Logs the error and notifies the user gracefully.
    """
    exception = update.exception
    actual_update: Update = update.update

    # Немедленно отвечаем на колбэк, чтобы у пользователя не "зависали" часы
    if actual_update.callback_query:
        with suppress(TelegramBadRequest):
            await actual_update.callback_query.answer()

    # Определяем язык пользователя для корректного ответа
    user = getattr(actual_update, "from_user", None)
    locale = user.language_code if user and user.language_code in i18n.available_locales else i18n.default_locale

    with i18n.context(), i18n.use_locale(locale):
        # Логируем полную информацию об ошибке
        try:
            update_details = actual_update.model_dump_json(exclude_none=True)
        except Exception:
            update_details = f"Could not serialize update object for update_id={actual_update.update_id}"

        logger.error(
            "An unhandled exception occurred in dispatcher",
            exc_info=exception,
            extra={"update": update_details}
        )

        # Формируем и отправляем вежливое сообщение пользователю
        error_message = _(
            "😔 Oops! Something went wrong on our end. "
            "Our team has been notified.\n\nPlease try again in a few moments or use /start to begin over."
        )

        target_message = actual_update.callback_query.message if actual_update.callback_query else actual_update.message

        if target_message:
            with suppress(TelegramBadRequest):
                await target_message.answer(error_message)

    return True
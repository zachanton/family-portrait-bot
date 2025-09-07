# aiogram_bot_template/handlers/settings.py
import asyncpg
import structlog
from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from aiogram.utils.i18n import I18n, gettext as _
from aiogram.fsm.storage.base import BaseStorage
from aiogram.fsm.storage.redis import RedisStorage

from aiogram_bot_template.db.db_api.storages import PostgresConnection
from aiogram_bot_template.db.repo.users import set_user_language
from aiogram_bot_template.states.user import Language
from aiogram_bot_template.keyboards.inline.callbacks import LanguageCallback
from aiogram_bot_template.keyboards.inline.language import language_kb
from . import menu

router = Router(name="settings-handlers")


@router.message(Command("language"), StateFilter("*"))
async def cmd_language(msg: Message, state: FSMContext, i18n: I18n) -> None:
    """
    Handles the /language command.
    """
    await state.set_state(Language.selecting)
    await msg.answer(_("Please select your language:"), reply_markup=language_kb(i18n))


@router.callback_query(
    LanguageCallback.filter(F.action == "select"), StateFilter(Language.selecting)
)
async def cq_select_language(
    cb: CallbackQuery,
    callback_data: LanguageCallback,
    db_pool: asyncpg.Pool,
    storage: BaseStorage,
    state: FSMContext,
    business_logger: structlog.typing.FilteringBoundLogger,
    i18n: I18n,
) -> None:
    """
    Processes language selection and prompts the user to restart the flow.
    """
    lang_code = callback_data.code
    user_id = cb.from_user.id

    db = PostgresConnection(db_pool, logger=business_logger)
    await set_user_language(db, user_id, lang_code)
    if isinstance(storage, RedisStorage):
        redis_key = f"user_lang:{user_id}"
        await storage.redis.set(redis_key, lang_code, ex=86400)

    with i18n.context(), i18n.use_locale(lang_code):
        await cb.message.edit_text(
            _("Language has been changed! Please send /start to begin a new generation.")
        )

    await state.clear()
    await cb.answer()
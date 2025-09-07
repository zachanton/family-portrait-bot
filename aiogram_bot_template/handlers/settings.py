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
from aiogram_bot_template.utils.re_prompt import re_prompt_for_state  # <--- IMPORT

router = Router(name="settings-handlers")


@router.message(Command("language"), StateFilter("*"))
async def cmd_language(msg: Message, state: FSMContext, i18n: I18n) -> None:
    """
    Handles the /language command.
    Saves the user's current state and prompts for a language change.
    """
    current_state = await state.get_state()
    current_data = await state.get_data()

    # Save the current state and data to return to it later
    await state.update_data(previous_state=current_state, previous_data=current_data)

    # Move the user to the language selection state
    await state.set_state(Language.selecting)
    await msg.answer(_("Please select your language:"), reply_markup=language_kb(i18n))


@router.callback_query(
    LanguageCallback.filter(F.action == "select"), StateFilter(Language.selecting)
)
async def cq_select_language(  # noqa: PLR0913, PLR0917
    cb: CallbackQuery,
    callback_data: LanguageCallback,
    db_pool: asyncpg.Pool,
    storage: BaseStorage,
    state: FSMContext,
    business_logger: structlog.typing.FilteringBoundLogger,
    i18n: I18n,
) -> None:
    """
    Processes language selection, returns the user to the previous state,
    and re-sends the corresponding prompt by editing the current message.
    """
    lang_code = callback_data.code
    user_id = cb.from_user.id

    # 1. Update language in the DB and cache
    db = PostgresConnection(db_pool, logger=business_logger, decode_json=True)
    await set_user_language(db, user_id, lang_code)
    if isinstance(storage, RedisStorage):
        redis_key = f"user_lang:{user_id}"
        await storage.redis.set(redis_key, lang_code, ex=86400)

    # 2. Restore the previous state and data
    user_data = await state.get_data()
    previous_state_str = user_data.get("previous_state")
    previous_data = user_data.get("previous_data", {})

    # Use the new locale for all subsequent messages
    with i18n.context(), i18n.use_locale(lang_code):
        # First, completely clear the current state (removing previous_state, etc.)
        await state.clear()

        # Then, restore the old data and state if it existed
        if previous_state_str:
            await state.set_state(previous_state_str)
            await state.set_data(previous_data)

        business_logger.info(
            "User changed language and returned to state",
            user_id=user_id,
            new_lang=lang_code,
            state=previous_state_str,
        )

        # Re-send the prompt for the restored state using the message from the callback
        if cb.message:
            await re_prompt_for_state(state, cb.message, i18n)

    await cb.answer()

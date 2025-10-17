# aiogram_bot_template/handlers/edit_handler.py
import asyncpg
import structlog
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, LinkPreviewOptions
from aiogram.filters import StateFilter
from aiogram.utils.i18n import gettext as _
from contextlib import suppress
from aiogram.exceptions import TelegramBadRequest

from aiogram_bot_template.data.constants import GenerationType
from aiogram_bot_template.states.user import Generation
from aiogram_bot_template.utils import moderation
from aiogram_bot_template.utils.status_manager import StatusMessageManager
from aiogram_bot_template.keyboards.inline.quality import quality_kb
from aiogram_bot_template.keyboards.inline.aspect_ratio import get_aspect_ratio_kb
from aiogram_bot_template.keyboards.inline.callbacks import ReframeImageCallback, SelectAspectRatioCallback
from aiogram_bot_template.db.db_api.storages import PostgresConnection
from aiogram_bot_template.db.repo import users as users_repo, generations as generations_repo
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

    status_msg = await message.answer(_("Checking your request... 📝"))
    status_manager = StatusMessageManager(
        bot=message.bot,
        chat_id=message.chat.id,
        message_id=status_msg.message_id,
        min_duration=1.0
    )
    
    is_safe = await moderation.is_safe_prompt(prompt)
    
    if not is_safe:
        await status_manager.update(
            _("This prompt seems to violate our safety policy. 🧐 Please try a different one.")
        )
        return

    await status_manager.update(_("Prompt accepted! Preparing options... ✅"))
    
    await state.update_data(
        user_prompt=prompt,
        generation_type=GenerationType.IMAGE_EDIT.value,
        is_reframe=False,  # Explicitly set flag for pipeline
    )

    db = PostgresConnection(db_pool, logger=business_logger)
    user_id = message.from_user.id
    
    is_in_whitelist = user_id in settings.free_trial_whitelist
    has_used_queue = True

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


@router.callback_query(ReframeImageCallback.filter(), StateFilter(Generation.waiting_for_next_action))
async def process_reframe_request(
    cb: CallbackQuery,
    callback_data: ReframeImageCallback,
    state: FSMContext,
    db_pool: asyncpg.Pool,
    business_logger: structlog.typing.FilteringBoundLogger,
) -> None:
    """
    Handles the 'Reframe' button press, fetches original generation type,
    sets the state, and asks for an aspect ratio.
    """
    await cb.answer()
    if not cb.message:
        return

    db = PostgresConnection(db_pool, logger=business_logger)
    sql = "SELECT type FROM generations WHERE id = $1"
    result = await db.fetchrow(sql, (callback_data.generation_id,))

    if not result or not result.data:
        await cb.message.answer(_("Sorry, I couldn't find that image to reframe. Please /start over."))
        await state.clear()
        return

    original_generation_type = result.data['type']

    await state.set_state(Generation.choosing_aspect_ratio)
    await state.update_data(
        source_generation_id=callback_data.generation_id,
        original_generation_type=original_generation_type,
        edit_source_message_id=cb.message.message_id,
    )

    caption_text = _(
        "🖼️ Please select the new aspect ratio for your portrait:\n\n"
        "<a href='https://telegra.ph/Rukovodstvo-po-sootnosheniyam-storon-Aspect-Ratios-10-17'>What do these numbers mean?</a>"
    )

    with suppress(TelegramBadRequest):
        await cb.message.edit_caption(
            caption=caption_text,
            reply_markup=get_aspect_ratio_kb(generation_id=callback_data.generation_id),
            link_preview_options=LinkPreviewOptions(is_disabled=True)
        )


# --- THE FIX IS HERE ---
@router.callback_query(SelectAspectRatioCallback.filter(), StateFilter(Generation.choosing_aspect_ratio))
async def process_aspect_ratio_selection(
    cb: CallbackQuery,
    callback_data: SelectAspectRatioCallback,
    state: FSMContext,
    db_pool: asyncpg.Pool,
    business_logger: structlog.typing.FilteringBoundLogger,
) -> None:
    """
    Handles aspect ratio selection, sets up the state for the pipeline,
    and proceeds to quality selection.
    """
    await cb.answer()
    if not cb.message:
        return

    db = PostgresConnection(db_pool, logger=business_logger)
    user_id = cb.from_user.id
    
    draft = generations_repo.GenerationRequestDraft(user_id=cb.from_user.id, status="editing", source_images=[])
    new_request_id = await generations_repo.create_generation_request(db, draft)

    await state.update_data(
        request_id=new_request_id,
        generation_type=GenerationType.IMAGE_EDIT.value,
        is_reframe=True,
        chosen_aspect_ratio=callback_data.ratio,
    )
    
    is_in_whitelist = user_id in settings.free_trial_whitelist
    has_used_queue = True

    await state.set_state(Generation.waiting_for_edit_quality)
    await cb.message.edit_caption(
        caption=_("Aspect ratio '{ratio}' selected! Now, please choose a package for this change:").format(
            ratio=callback_data.ratio
        ),
        reply_markup=quality_kb(
            generation_type=GenerationType.IMAGE_EDIT,
            is_trial_available=is_in_whitelist,
            is_live_queue_available=not has_used_queue
        )
    )

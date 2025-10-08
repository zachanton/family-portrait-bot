# aiogram_bot_template/handlers/next_step_handler.py
import asyncio
import asyncpg
import structlog
from aiogram import F, Router, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from aiogram.filters import StateFilter
from aiogram.utils.i18n import gettext as _
from contextlib import suppress
from aiogram.exceptions import TelegramBadRequest
from typing import Set

from . import menu
from aiogram_bot_template.data.constants import GenerationType, ImageRole
from aiogram_bot_template.db.db_api.storages import PostgresConnection
from aiogram_bot_template.db.repo import generations as generations_repo, users as users_repo
from aiogram_bot_template.keyboards.inline.callbacks import (
    RetryGenerationCallback, ContinueWithImageCallback, CreateFamilyPhotoCallback,
    ContinueWithFamilyPhotoCallback, ContinueWithPairPhotoCallback, SessionActionCallback
)
from aiogram_bot_template.keyboards.inline import (
    child_selection as child_selection_kb, 
    family_selection as family_selection_kb,
    pair_selection as pair_selection_kb,
    session_actions as session_actions_kb,
)
from aiogram_bot_template.keyboards.inline.gender import gender_kb
from aiogram_bot_template.keyboards.inline.quality import quality_kb
from aiogram_bot_template.states.user import Generation
from aiogram_bot_template.data.settings import settings
from .menu import _cleanup_session_menu, _cleanup_full_session

router = Router(name="next-step-handler")


async def _process_session_action_async(
    cb: CallbackQuery,
    callback_data: SessionActionCallback,
    state: FSMContext,
    db_pool: asyncpg.Pool,
    business_logger: structlog.typing.FilteringBoundLogger,
    bot: Bot,
):
    # This background task handles the slow logic for session actions.
    await _cleanup_session_menu(bot, cb.message.chat.id, state)
    
    status_msg = await cb.message.answer(_("Got it! Preparing the new generation..."))

    user_data = await state.get_data()
    db = PostgresConnection(db_pool, logger=business_logger)
    user_id = cb.from_user.id
    action_type = GenerationType(callback_data.action_type)

    parent_composite_uid = user_data.get("parent_composite_uid")
    if not parent_composite_uid:
        await status_msg.edit_text(_("I couldn't find the parent data for this session. Please /start over."))
        await state.clear()
        return

    draft = generations_repo.GenerationRequestDraft(
        user_id=user_id, status="params_collected_session", source_images=[]
    )
    new_request_id = await generations_repo.create_generation_request(db, draft)
    
    await state.update_data(
        request_id=new_request_id,
        generation_type=action_type.value,
        next_step_message_id=None
    )
    
    await status_msg.delete()
    if action_type == GenerationType.CHILD_GENERATION:
        await state.set_state(Generation.choosing_child_gender)
        await cb.message.answer(
            _("Let's create another child portrait! Please choose the desired gender:"),
            reply_markup=gender_kb()
        )
    elif action_type == GenerationType.PAIR_PHOTO:
        is_in_whitelist = user_id in settings.free_trial_whitelist
        has_used_trial = await users_repo.get_user_trial_status(db, user_id)
        is_trial_available = is_in_whitelist or not has_used_trial

        await state.set_state(Generation.waiting_for_quality)
        await cb.message.answer(
            _("Excellent! Please choose a generation package for your couple portrait:"),
            reply_markup=quality_kb(
                generation_type=GenerationType.PAIR_PHOTO,
                is_trial_available=is_trial_available
            )
        )

@router.callback_query(SessionActionCallback.filter(), StateFilter(Generation.waiting_for_next_action))
async def process_session_action(
    cb: CallbackQuery,
    callback_data: SessionActionCallback,
    state: FSMContext,
    db_pool: asyncpg.Pool,
    business_logger: structlog.typing.FilteringBoundLogger,
    bot: Bot,
):
    # Immediately answer the callback
    await cb.answer()
    if not cb.message:
        return

    # Offload the rest of the logic to a background task
    asyncio.create_task(_process_session_action_async(
        cb, callback_data, state, db_pool, business_logger, bot
    ))


@router.callback_query(F.data == "return_to_session_menu", StateFilter(Generation.waiting_for_next_action))
async def return_to_session_menu(
    cb: CallbackQuery,
    state: FSMContext,
    bot: Bot,
) -> None:
    await cb.answer()
    if not cb.message:
        return

    with suppress(TelegramBadRequest):
        await cb.message.delete()
    
    user_data = await state.get_data()
    generated_in_session: Set[str] = set(user_data.get("generated_in_session", []))

    session_actions_msg = await bot.send_message(
        chat_id=cb.message.chat.id,
        text=_("✨ Your portraits are ready!\n\n"
             "Select your favorite one from the images above, or choose another action below."),
        reply_markup=session_actions_kb.session_actions_kb(generated_in_session)
    )
    await state.update_data(next_step_message_id=session_actions_msg.message_id)


@router.callback_query(F.data == "start_new", StateFilter("*"))
async def start_new_generation(
    callback: CallbackQuery,
    state: FSMContext,
):
    await callback.answer()
    
    if not callback.message:
        await menu.send_welcome_message(callback.message, state, is_restart=True)
        return

    await _cleanup_full_session(callback.bot, callback.message.chat.id, state)
    
    with suppress(TelegramBadRequest):
        await callback.message.delete()
            
    await menu.send_welcome_message(callback.message, state, is_restart=True)


async def _process_retry_generation_async(
    cb: CallbackQuery,
    callback_data: RetryGenerationCallback,
    state: FSMContext,
    db_pool: asyncpg.Pool,
    business_logger: structlog.typing.FilteringBoundLogger,
    bot: Bot,
):
    # This background task handles the slow logic for retrying a generation.
    await _cleanup_full_session(bot, cb.message.chat.id, state)
    with suppress(TelegramBadRequest):
        await cb.message.delete()
    
    db = PostgresConnection(db_pool, logger=business_logger)
    original_request = await generations_repo.get_request_details_with_sources(
        db, callback_data.request_id
    )
    if not original_request or not original_request.get("source_images"):
        await cb.message.answer(
            _("I couldn't find the original photos. Please start over with /start.")
        )
        return

    parent_source_images_dto = [
        (img["file_unique_id"], img["file_id"], img["role"])
        for img in original_request["source_images"] if img["role"] in [ImageRole.FATHER.value, ImageRole.MOTHER.value]
    ]

    draft = generations_repo.GenerationRequestDraft(
        user_id=cb.from_user.id, status="photos_collected", source_images=parent_source_images_dto
    )
    new_request_id = await generations_repo.create_generation_request(db, draft)

    await state.set_state(Generation.choosing_child_gender)
    await state.update_data(
        request_id=new_request_id,
        photos_collected=[
            {"file_id": img[1], "file_unique_id": img[0], "role": img[2]} for img in parent_source_images_dto
        ],
        is_retry=True,
        generation_type=GenerationType.CHILD_GENERATION.value,
        photo_message_ids=[], next_step_message_id=None
    )

    await cb.message.answer(
        _("Let's try again! Please choose the desired gender for the child:"),
        reply_markup=gender_kb(),
    )

@router.callback_query(RetryGenerationCallback.filter(), StateFilter(Generation.waiting_for_next_action))
async def process_retry_generation(
    cb: CallbackQuery,
    callback_data: RetryGenerationCallback,
    state: FSMContext,
    db_pool: asyncpg.Pool,
    business_logger: structlog.typing.FilteringBoundLogger,
    bot: Bot,
):
    await cb.answer()
    if not cb.message:
        return
    
    asyncio.create_task(_process_retry_generation_async(
        cb, callback_data, state, db_pool, business_logger, bot
    ))


async def _process_continue_with_image_async(
    cb: CallbackQuery,
    callback_data: ContinueWithImageCallback,
    state: FSMContext,
    db_pool: asyncpg.Pool,
    business_logger: structlog.typing.FilteringBoundLogger,
    bot: Bot,
):
    # This background task handles the slow logic for selecting a child image.
    await _cleanup_session_menu(bot, cb.message.chat.id, state)

    db = PostgresConnection(db_pool, logger=business_logger)
    sql = "SELECT result_file_id FROM generations WHERE id = $1"
    result = await db.fetchrow(sql, (callback_data.generation_id,))
    
    if not result or not result.data or not result.data.get("result_file_id"):
        await cb.message.answer(_("I couldn't find the selected image. Please start over with /start."))
        await state.clear()
        return

    selected_file_id = result.data["result_file_id"]

    sent_message = await bot.send_photo(
        chat_id=cb.message.chat.id,
        photo=selected_file_id,
        caption=_("Great choice! What's next for this portrait?"),
        reply_markup=child_selection_kb.post_child_selection_kb(
            generation_id=callback_data.generation_id,
            request_id=callback_data.request_id
        )
    )
    
    await state.update_data(
        selected_child_generation_id=callback_data.generation_id,
        next_step_message_id=sent_message.message_id
    )

@router.callback_query(ContinueWithImageCallback.filter(), StateFilter(Generation.waiting_for_next_action))
async def process_continue_with_image(
    cb: CallbackQuery,
    callback_data: ContinueWithImageCallback,
    state: FSMContext,
    db_pool: asyncpg.Pool,
    business_logger: structlog.typing.FilteringBoundLogger,
    bot: Bot,
):
    await cb.answer()
    if not cb.message:
        return
    
    asyncio.create_task(_process_continue_with_image_async(
        cb, callback_data, state, db_pool, business_logger, bot
    ))


async def _process_continue_with_family_photo_async(
    cb: CallbackQuery,
    callback_data: ContinueWithFamilyPhotoCallback,
    state: FSMContext,
    db_pool: asyncpg.Pool,
    business_logger: structlog.typing.FilteringBoundLogger,
    bot: Bot,
):
    # This background task handles the slow logic for selecting a family photo.
    await _cleanup_session_menu(bot, cb.message.chat.id, state)
    
    db = PostgresConnection(db_pool, logger=business_logger)
    sql = "SELECT result_file_id FROM generations WHERE id = $1"
    result = await db.fetchrow(sql, (callback_data.generation_id,))
    if not result or not result.data or not result.data.get("result_file_id"):
        await cb.message.answer(_("I couldn't find the selected image. Please start over with /start."))
        await state.clear()
        return

    selected_file_id = result.data["result_file_id"]

    sent_message = await bot.send_photo(
        chat_id=cb.message.chat.id,
        photo=selected_file_id,
        caption=_("A wonderful choice! \n\nWhat would you like to do next?"),
        reply_markup=family_selection_kb.post_family_photo_selection_kb()
    )
    await state.update_data(next_step_message_id=sent_message.message_id)

@router.callback_query(ContinueWithFamilyPhotoCallback.filter(), StateFilter(Generation.waiting_for_next_action))
async def process_continue_with_family_photo(
    cb: CallbackQuery,
    callback_data: ContinueWithFamilyPhotoCallback,
    state: FSMContext,
    db_pool: asyncpg.Pool,
    business_logger: structlog.typing.FilteringBoundLogger,
    bot: Bot,
):
    await cb.answer()
    if not cb.message:
        return
    
    asyncio.create_task(_process_continue_with_family_photo_async(
        cb, callback_data, state, db_pool, business_logger, bot
    ))


async def _process_continue_with_pair_photo_async(
    cb: CallbackQuery,
    callback_data: ContinueWithPairPhotoCallback,
    state: FSMContext,
    db_pool: asyncpg.Pool,
    business_logger: structlog.typing.FilteringBoundLogger,
    bot: Bot,
):
    # This background task handles the slow logic for selecting a pair photo.
    await _cleanup_session_menu(bot, cb.message.chat.id, state)

    db = PostgresConnection(db_pool, logger=business_logger)
    sql = "SELECT result_file_id FROM generations WHERE id = $1"
    result = await db.fetchrow(sql, (callback_data.generation_id,))
    if not result or not result.data or not result.data.get("result_file_id"):
        await cb.message.answer(_("I couldn't find the selected image. Please start over with /start."))
        await state.clear()
        return

    selected_file_id = result.data["result_file_id"]
    
    sent_message = await bot.send_photo(
        chat_id=cb.message.chat.id,
        photo=selected_file_id,
        caption=_("An excellent choice! \n\nWhat would you like to do next?"),
        reply_markup=pair_selection_kb.post_pair_photo_selection_kb()
    )
    await state.update_data(next_step_message_id=sent_message.message_id)

@router.callback_query(ContinueWithPairPhotoCallback.filter(), StateFilter(Generation.waiting_for_next_action))
async def process_continue_with_pair_photo(
    cb: CallbackQuery,
    callback_data: ContinueWithPairPhotoCallback,
    state: FSMContext,
    db_pool: asyncpg.Pool,
    business_logger: structlog.typing.FilteringBoundLogger,
    bot: Bot,
):
    await cb.answer()
    if not cb.message:
        return
    
    asyncio.create_task(_process_continue_with_pair_photo_async(
        cb, callback_data, state, db_pool, business_logger, bot
    ))


async def _process_create_family_photo_async(
    cb: CallbackQuery,
    callback_data: CreateFamilyPhotoCallback,
    state: FSMContext,
    db_pool: asyncpg.Pool,
    business_logger: structlog.typing.FilteringBoundLogger,
    bot: Bot,
):
    # This background task handles the slow logic for creating a family photo.
    with suppress(TelegramBadRequest):
        await cb.message.delete()
        
    status_msg = await bot.send_message(
        chat_id=cb.message.chat.id,
        text=_("Got it! Preparing the family photoshoot...")
    )

    db = PostgresConnection(db_pool, logger=business_logger)
    user_id = cb.from_user.id
    user_data = await state.get_data()
    
    try:
        mom_profile_uid = user_data.get("mom_profile_uid")
        dad_profile_uid = user_data.get("dad_profile_uid")
        if not mom_profile_uid or not dad_profile_uid:
            raise ValueError("Could not find parent visual UIDs in session state.")

        parent_sources = [
            {"file_unique_id": mom_profile_uid, "file_id": f"vr_mom_{mom_profile_uid}", "role": ImageRole.MOTHER_HORIZONTAL.value},
            {"file_unique_id": dad_profile_uid, "file_id": f"vr_dad_{dad_profile_uid}", "role": ImageRole.FATHER_HORIZONTAL.value},
        ]
        
        sql_child = "SELECT result_image_unique_id, result_file_id FROM generations WHERE id = $1"
        child_res = await db.fetchrow(sql_child, (callback_data.child_generation_id,))
        if not child_res.data:
            raise ValueError("Could not find the selected child's image data.")
        
        child_source = {
            "file_unique_id": child_res.data["result_image_unique_id"],
            "file_id": child_res.data["result_file_id"],
            "role": ImageRole.CHILD.value,
        }

        all_sources = parent_sources + [child_source]
        source_images_dto = [(img["file_unique_id"], img["file_id"], img["role"]) for img in all_sources]

        draft = generations_repo.GenerationRequestDraft(
            user_id=user_id, status="params_collected", source_images=source_images_dto
        )
        new_request_id = await generations_repo.create_generation_request(db, draft)
        
        await state.update_data(
            request_id=new_request_id,
            generation_type=GenerationType.FAMILY_PHOTO.value,
            photos_collected=all_sources,
            next_step_message_id=None
        )

        is_in_whitelist = user_id in settings.free_trial_whitelist
        has_used_trial = await users_repo.get_user_trial_status(db, user_id)
        is_trial_available = is_in_whitelist or not has_used_trial

        await status_msg.edit_text(
            _("Ready for the family portrait! Please choose your generation package:"),
            reply_markup=quality_kb(
                generation_type=GenerationType.FAMILY_PHOTO,
                is_trial_available=is_trial_available
            ),
        )
        await state.set_state(Generation.waiting_for_quality)

    except Exception as e:
        business_logger.exception("Failed to start family photo flow", error=e)
        await status_msg.edit_text(_("Sorry, something went wrong. Please /start over."))
        await state.clear()

@router.callback_query(CreateFamilyPhotoCallback.filter(), StateFilter(Generation.waiting_for_next_action))
async def process_create_family_photo(
    cb: CallbackQuery,
    callback_data: CreateFamilyPhotoCallback,
    state: FSMContext,
    db_pool: asyncpg.Pool,
    business_logger: structlog.typing.FilteringBoundLogger,
    bot: Bot,
):
    await cb.answer()
    if not cb.message:
        return
    
    asyncio.create_task(_process_create_family_photo_async(
        cb, callback_data, state, db_pool, business_logger, bot
    ))
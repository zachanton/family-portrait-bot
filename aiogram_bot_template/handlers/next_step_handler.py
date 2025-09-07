# aiogram_bot_template/handlers/next_step_handler.py
import json
import asyncio
import asyncpg
import structlog
import uuid
from redis.asyncio import Redis

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from aiogram.filters import StateFilter
from aiogram.utils.i18n import gettext as _

from aiogram_bot_template.data.constants import GenerationType, ImageRole, SessionContextType
from aiogram_bot_template.data.settings import settings
from aiogram_bot_template.db.db_api.storages import PostgresConnection
from aiogram_bot_template.db.repo import generations as generations_repo, users as users_repo
from aiogram_bot_template.keyboards.inline import edit_prompts, generation_quality, next_step, quality
from aiogram_bot_template.keyboards.inline.callbacks import (
    ContinueEditingCallback, GetHdCallback, RetryGenerationCallback,
    EditChildParamsCallback, ShowNextStepSubmenu, ReturnToMainMenu,
    CreateGroupPhotoCallback, ReturnToGenerationCallback
)
from aiogram_bot_template.keyboards.inline.child_age import age_selection_kb
from aiogram_bot_template.states.user import Generation
from aiogram_bot_template.handlers import menu
from aiogram_bot_template.utils.parameter_parser import extract_latest_parameters
from aiogram_bot_template.dto.post_generation_context import PostGenerationContext
from aiogram_bot_template.dto.facial_features import ImageDescription
from aiogram_bot_template.handlers.menu import _deactivate_all_previous_generations

from contextlib import suppress
from aiogram.exceptions import TelegramBadRequest


router = Router(name="next-step-handler")


# This handler is fast enough, no need for a background task.
@router.callback_query(ShowNextStepSubmenu.filter(), StateFilter("*"))
async def show_submenu(cb: CallbackQuery, callback_data: ShowNextStepSubmenu, state: FSMContext):
    await cb.answer()
    markup = None
    if callback_data.menu == "improve":
        markup = next_step.improve_submenu_kb(callback_data.key, callback_data.request_id)
    elif callback_data.menu == "retry":
        markup = next_step.retry_submenu_kb(callback_data.key, callback_data.request_id)
    if markup:
        await cb.message.edit_reply_markup(reply_markup=markup)


async def _process_return_to_main_menu_async(
    cb: CallbackQuery,
    callback_data: ReturnToMainMenu,
    state: FSMContext,
    db_pool: asyncpg.Pool,
    business_logger: structlog.typing.FilteringBoundLogger,
):
    user_data = await state.get_data()
    # Get the CURRENT session context from the FSM state
    session_context_str = user_data.get("session_context", SessionContextType.CHILD_GENERATION.value)
    session_context = SessionContextType(session_context_str)

    markup = next_step.get_next_step_keyboard(
        context=session_context, 
        continue_key=callback_data.key, 
        request_id=callback_data.request_id
    )

    if cb.message:
        with suppress(TelegramBadRequest):
            await cb.message.edit_text(
                _("What would you like to do next?"),
                reply_markup=markup
            )
    await state.set_state(Generation.waiting_for_next_action)


async def _process_continue_editing_async(
    cb: CallbackQuery,
    callback_data: ContinueEditingCallback,
    state: FSMContext,
    cache_pool: Redis,
    db_pool: asyncpg.Pool,
    business_logger: structlog.typing.FilteringBoundLogger,
):
    stored_data_json = await cache_pool.get(f"continue_edit:{callback_data.key}")
    if not stored_data_json:
        await cb.message.edit_text(_("This link has expired. Please start over."), reply_markup=None)
        return

    try:
        context = PostGenerationContext.model_validate_json(stored_data_json)
    except Exception:
        await cb.message.edit_text(_("This link has expired or the data is corrupted. Please start over."), reply_markup=None)
        return

    db = PostgresConnection(db_pool, logger=business_logger)
    source_images_dto = [(context.unique_id, context.file_id, ImageRole.BASE)]
    draft = generations_repo.GenerationRequestDraft(
        user_id=cb.from_user.id, status="photos_collected", referral_source=None,
        source_images=source_images_dto, request_parameters={},
    )
    new_request_id = await generations_repo.create_generation_request(db, draft)
    business_logger.info("New GenerationRequest created for image edit", request_id=new_request_id)

    # Replaced state.clear() and state.set_data() with state.update_data()
    # to preserve active message IDs from the previous state.
    old_user_data = await state.get_data()
    root_request_id = old_user_data.get("root_request_id")
    

    next_gen_type = (
        GenerationType.GROUP_PHOTO_EDIT
        if context.generation_type == GenerationType.GROUP_PHOTO
        else GenerationType.IMAGE_EDIT
    )
    # This determines which edit menu to show.
    source_type_for_menu = (
        GenerationType.GROUP_PHOTO
        if context.generation_type == GenerationType.GROUP_PHOTO
        else GenerationType.CHILD_GENERATION
    )

    await state.update_data({
        "request_id": new_request_id,
        "generation_type": next_gen_type.value,
        "source_generation_type_for_edit": source_type_for_menu.value,
        "photos_needed": 1,
        "photos_collected": [{"file_id": context.file_id, "file_unique_id": context.unique_id}],
        "parent_descriptions": context.context.parent_descriptions,
        "child_description": context.context.child_description.model_dump() if context.context.child_description else None,
        "continue_key": callback_data.key,
        "original_request_id": context.request_id,
        "root_request_id": root_request_id,
        "session_context": context.context.session_context.value,
    })

    data = await state.get_data()
    child_desc_model = ImageDescription.model_validate(data["child_description"]) if data.get("child_description") else None
    
    reply_markup = edit_prompts.create_edit_menu_kb(
        back_continue_key=callback_data.key,
        back_request_id=context.request_id,
        child_description=child_desc_model,
        parent_descriptions=data.get("parent_descriptions"),
        generation_type=source_type_for_menu,
        path=None,
    )
    
    await cb.message.edit_text(
        _("Ready to get creative! Please choose a category to begin editing:"),
        reply_markup=reply_markup,
    )
    await state.set_state(Generation.waiting_for_prompt)


async def _process_hd_request_async(
    cb: CallbackQuery,
    callback_data: GetHdCallback,
    state: FSMContext,
    cache_pool: Redis,
    db_pool: asyncpg.Pool,
    business_logger: structlog.typing.FilteringBoundLogger,
):
    stored_data_json = await cache_pool.get(f"continue_edit:{callback_data.key}")
    if not stored_data_json:
        await cb.message.edit_text(_("This link has expired."), reply_markup=None)
        return

    try:
        context = PostGenerationContext.model_validate_json(stored_data_json)
    except Exception:
        await cb.message.edit_text(_("This link has expired or the data is corrupted. Please start over."), reply_markup=None)
        return

    db = PostgresConnection(db_pool, logger=business_logger)
    source_images_dto = [(context.unique_id, context.file_id, ImageRole.UPSCALE_SOURCE)]
    draft = generations_repo.GenerationRequestDraft(
        user_id=cb.from_user.id, status="photos_collected", referral_source=None,
        source_images=source_images_dto, request_parameters={},
    )
    new_request_id = await generations_repo.create_generation_request(db, draft)

    # Replaced state.clear() and state.set_data() with state.update_data()
    old_user_data = await state.get_data()
    root_request_id = old_user_data.get("root_request_id")
    current_session_context = context.context.session_context

    effective_source_for_pipeline = GenerationType.CHILD_GENERATION
    if current_session_context in [SessionContextType.GROUP_PHOTO, SessionContextType.EDITED_GROUP_PHOTO]:
        effective_source_for_pipeline = GenerationType.GROUP_PHOTO

    await state.update_data({
        "request_id": new_request_id,
        "generation_type": GenerationType.UPSCALE.value,
        "session_context": current_session_context.value, 
        "parent_descriptions": context.context.parent_descriptions,
        "child_description": context.context.child_description.model_dump() if context.context.child_description else None,
        "root_request_id": root_request_id,
        "effective_source_type_for_upscale": effective_source_for_pipeline.value,
    })

    user_id = cb.from_user.id
    is_in_whitelist = user_id in settings.free_trial_whitelist
    has_used_trial = await users_repo.get_user_trial_status(db, user_id)
    is_trial_available = is_in_whitelist or not has_used_trial

    await cb.message.edit_text(
        _("Please select the desired HD quality:"),
        reply_markup=quality.upscale_quality_kb(
            is_trial_available=is_trial_available,
            continue_key=callback_data.key,
            request_id=context.request_id
        ),
    )
    await state.set_state(Generation.waiting_for_quality)


async def _process_create_group_photo_async(
    cb: CallbackQuery,
    callback_data: CreateGroupPhotoCallback,
    state: FSMContext,
    cache_pool: Redis,
    db_pool: asyncpg.Pool,
    business_logger: structlog.typing.FilteringBoundLogger,
):
    stored_data_json = await cache_pool.get(f"continue_edit:{callback_data.key}")
    if not stored_data_json:
        await cb.message.edit_text(_("This session has expired. Please start over."), reply_markup=None)
        return

    try:
        context = PostGenerationContext.model_validate_json(stored_data_json)
    except Exception:
        await cb.message.edit_text(_("Session data is corrupted. Please start over."), reply_markup=None)
        return

    db = PostgresConnection(db_pool, logger=business_logger)
    
    user_data = await state.get_data()
    root_request_id = user_data.get("root_request_id")

    if not root_request_id:
        await cb.message.edit_text(_("Could not find the original parent photos session. Please start over."), reply_markup=None)
        return

    original_request = await generations_repo.get_request_details_with_sources(db, root_request_id)
    if not original_request or len(original_request.get("source_images", [])) < 2:
        await cb.message.edit_text(_("Could not find the original parent photos. Please start over."), reply_markup=None)
        return

    parent_photos = {p['role']: p for p in original_request["source_images"]}
    parent1 = parent_photos.get(ImageRole.PARENT_1)
    parent2 = parent_photos.get(ImageRole.PARENT_2)

    if not parent1 or not parent2:
        await cb.message.edit_text(_("Could not identify original parent photos correctly. Please start over."), reply_markup=None)
        return

    source_images_dto = [
        (parent1["file_unique_id"], parent1["file_id"], ImageRole.GROUP_PHOTO_PARENT_1),
        (parent2["file_unique_id"], parent2["file_id"], ImageRole.GROUP_PHOTO_PARENT_2),
        (context.unique_id, context.file_id, ImageRole.GROUP_PHOTO_CHILD),
    ]

    draft = generations_repo.GenerationRequestDraft(
        user_id=cb.from_user.id, status="photos_collected", referral_source=None,
        source_images=source_images_dto, request_parameters={},
    )
    new_request_id = await generations_repo.create_generation_request(db, draft)

    # Replaced state.clear() and state.set_data() with state.update_data()
    await state.update_data({
        "request_id": new_request_id,
        "generation_type": GenerationType.GROUP_PHOTO.value,
        "parent_descriptions": context.context.parent_descriptions,
        "child_description": context.context.child_description.model_dump() if context.context.child_description else None,
        "continue_key": callback_data.key,
        "original_request_id": context.request_id,
        "root_request_id": root_request_id,
    })
    
    user_id = cb.from_user.id
    is_in_whitelist = user_id in settings.free_trial_whitelist
    has_used_trial = await users_repo.get_user_trial_status(db, user_id)
    is_trial_available = is_in_whitelist or not has_used_trial
    
    await cb.message.edit_text(
        _("Great! All three photos are ready. Now, please select the quality for the family portrait:"),
        reply_markup=generation_quality.generation_quality_kb(
            is_trial_available=is_trial_available,
            generation_type=GenerationType.GROUP_PHOTO,
            continue_key=callback_data.key,
            request_id=context.request_id
        ),
    )
    await state.set_state(Generation.waiting_for_quality)


async def _process_start_new_generation_async(
    cb: CallbackQuery,
    state: FSMContext,
    bot: Bot,
    db_pool: asyncpg.Pool,
    business_logger: structlog.typing.FilteringBoundLogger,
):
    # Deactivate previous generations before clearing the state
    db = PostgresConnection(db_pool, logger=business_logger)
    await _deactivate_all_previous_generations(cb.from_user.id, bot, db, state, business_logger)

    await state.clear()
    if cb.message:
        # Create a new message because we can't edit the old one into the start message
        await menu._send_welcome_message_and_set_state(
            cb.message, state, is_restart=True
        )
        # Delete the message with the "Start new" button to clean up the chat
        with suppress(TelegramBadRequest):
            await cb.message.delete()


async def _process_retry_generation_async(
    cb: CallbackQuery, callback_data: RetryGenerationCallback, state: FSMContext,
    db_pool: asyncpg.Pool, business_logger: structlog.typing.FilteringBoundLogger
):
    user_data = await state.get_data()
    request_id_from_callback = callback_data.request_id
    continue_key = user_data.get("continue_key")
    root_request_id = user_data.get("root_request_id")
    
    # --- ADD THIS LINE ---
    parent_descriptions = user_data.get("parent_descriptions") # Preserve existing descriptions

    db = PostgresConnection(db_pool, logger=business_logger)
    
    original_request = await _load_original_request(db_pool, request_id_from_callback, business_logger)
    if not original_request:
        await cb.message.edit_text(_("Could not find the original data. Please start over."), reply_markup=None)
        return
        
    original_gen_type_str = await generations_repo.get_original_generation_type(db, request_id_from_callback)
    original_gen_type = GenerationType(original_gen_type_str or GenerationType.CHILD_GENERATION)

    source_images_roles_map = {
        GenerationType.CHILD_GENERATION: [ImageRole.PARENT_1, ImageRole.PARENT_2],
        GenerationType.GROUP_PHOTO: [ImageRole.GROUP_PHOTO_PARENT_1, ImageRole.GROUP_PHOTO_PARENT_2, ImageRole.GROUP_PHOTO_CHILD],
    }
    
    source_images_dto = [
        (img["file_unique_id"], img["file_id"], img["role"])
        for img in original_request["source_images"]
        if img["role"] in source_images_roles_map.get(original_gen_type, [])
    ]
    
    draft = generations_repo.GenerationRequestDraft(
        user_id=cb.from_user.id, status="photos_collected", referral_source=None,
        source_images=source_images_dto, request_parameters={},
    )
    new_request_id = await generations_repo.create_generation_request(db, draft)
    
    params = extract_latest_parameters(original_request.get("request_parameters"))

    # Replaced state.clear() and state.set_data() with state.update_data()
    new_data = {
        "request_id": new_request_id,
        "generation_type": original_gen_type.value,
        "photos_collected": [
            {"file_id": img[1], "file_unique_id": img[0]}
            for img in source_images_dto
        ],
        "is_retry": True,
        "root_request_id": root_request_id,
        "parent_descriptions": parent_descriptions, # <-- AND ADD THIS LINE
    }
    new_data.update(params)
    await state.update_data(new_data)
    
    user_id = cb.from_user.id

    is_in_whitelist = user_id in settings.free_trial_whitelist
    has_used_trial = await users_repo.get_user_trial_status(db, user_id)
    is_trial_available = is_in_whitelist or not has_used_trial

    await cb.message.edit_text(
        _("Original photos loaded! Please select a quality for the new variation:"),
        reply_markup=generation_quality.generation_quality_kb(
            is_trial_available=is_trial_available,
            generation_type=original_gen_type,
            continue_key=continue_key,
            request_id=new_request_id
        )
    )
    await state.set_state(Generation.waiting_for_quality)


async def _process_edit_child_params_async(
    cb: CallbackQuery, callback_data: EditChildParamsCallback, state: FSMContext,
    db_pool: asyncpg.Pool, business_logger: structlog.typing.FilteringBoundLogger
):
    user_data = await state.get_data()
    request_id = callback_data.request_id
    continue_key = user_data.get("continue_key")
    root_request_id = user_data.get("root_request_id")

    parent_descriptions = user_data.get("parent_descriptions")

    original_request = await _load_original_request(db_pool, request_id, business_logger)
    if not original_request:
        await cb.message.edit_text(_("Could not find the original data. Please start over."), reply_markup=None)
        return

    photos_collected = [
        {"file_id": img["file_id"], "file_unique_id": img["file_unique_id"]}
        for img in original_request["source_images"]
    ]
    params = extract_latest_parameters(original_request.get("request_parameters"))

    new_data = {
        "request_id": request_id,
        "generation_type": GenerationType.CHILD_GENERATION.value,
        "photos_collected": photos_collected,
        "is_retry": True,
        "root_request_id": root_request_id,
        "parent_descriptions": parent_descriptions,
    }
    new_data.update(params)
    await state.update_data(new_data)
    await state.update_data(continue_key=continue_key)

    await cb.message.edit_text(
        _("Let's try different parameters! Please choose the desired age group:"),
        reply_markup=age_selection_kb()
    )
    await state.set_state(Generation.waiting_for_options)


async def _process_reactivate_generation_async(
    cb: CallbackQuery,
    callback_data: ReturnToGenerationCallback,
    state: FSMContext,
    bot: Bot,
    db_pool: asyncpg.Pool,
    cache_pool: Redis,
    business_logger: structlog.typing.FilteringBoundLogger,
):
    log = business_logger.bind(reactivate_gen_id=callback_data.generation_id)
    db = PostgresConnection(db_pool, logger=log)
    
    user_data = await state.get_data()
    root_request_id = user_data.get("root_request_id")
    
    generation_to_reactivate = await generations_repo.get_generation_details(db, callback_data.generation_id)
    if not generation_to_reactivate:
        await cb.answer(_("This generation has expired or could not be found."), show_alert=True)
        return

    current_active_gen_id = user_data.get("active_generation_id")
    if current_active_gen_id and current_active_gen_id != callback_data.generation_id:
        current_active_details = await generations_repo.get_generation_details(db, current_active_gen_id)
        if current_active_details:
            log.info("Deactivating current active session", gen_id=current_active_gen_id)
            with suppress(TelegramBadRequest):
                await bot.delete_message(
                    chat_id=cb.message.chat.id,
                    message_id=current_active_details["control_message_id"],
                )
                await bot.edit_message_reply_markup(
                    chat_id=cb.message.chat.id,
                    message_id=current_active_details["result_message_id"],
                    reply_markup=next_step.get_return_to_generation_kb(current_active_gen_id)
                )
            
            # Nullify message IDs in the database for the deactivated session
            # to prevent it from being processed again by global cleanup.
            sql_update_deactivated = """
                UPDATE generations
                SET result_message_id = NULL, control_message_id = NULL
                WHERE id = $1;
            """
            await db.execute(sql_update_deactivated, (current_active_gen_id,))
            log.info("Deactivated generation nulled in DB", gen_id=current_active_gen_id)

    # Clean up the old messages for the generation we are about to reactivate
    with suppress(TelegramBadRequest):
        # We need to use cb.message.chat.id because the message might be from a different chat
        # in some edge cases, but for this bot it's always the same.
        if generation_to_reactivate["result_message_id"]:
             await bot.delete_message(cb.message.chat.id, generation_to_reactivate["result_message_id"])
    with suppress(TelegramBadRequest):
        if generation_to_reactivate["control_message_id"]:
            await bot.delete_message(cb.message.chat.id, generation_to_reactivate["control_message_id"])

    # 1. Recreate the context from the database record
    context_from_db = PostGenerationContext.from_db_record(generation_to_reactivate)
    
    # 2. Extract the session context from the stored metadata
    session_context = context_from_db.context.session_context

    # 3. Re-send content and create the correct keyboard
    sent_photo_msg = None
    if context_from_db.generation_type == GenerationType.UPSCALE:
        sent_photo_msg = await bot.send_document(cb.message.chat.id, document=context_from_db.file_id, caption=generation_to_reactivate.get("caption"))
    else:
        sent_photo_msg = await bot.send_photo(cb.message.chat.id, photo=context_from_db.file_id, caption=generation_to_reactivate.get("caption"))
    
    continue_key = uuid.uuid4().hex[:16]
    request_id = context_from_db.request_id
    
    control_message_text = _("What would you like to do next?")
    reply_markup = next_step.get_next_step_keyboard(
        context=session_context, 
        continue_key=continue_key, 
        request_id=request_id,
    )
    new_control_message = await bot.send_message(cb.message.chat.id, control_message_text, reply_markup=reply_markup)

    await cache_pool.set(f"continue_edit:{continue_key}", context_from_db.model_dump_json(), ex=86400)
    
    await db.execute(
        "UPDATE generations SET result_message_id = $1, control_message_id = $2 WHERE id = $3",
        (sent_photo_msg.message_id, new_control_message.message_id, callback_data.generation_id)
    )

    # 4. Update the FSM with the fully restored context
    await state.clear()
    await state.set_state(Generation.waiting_for_next_action)
    await state.update_data(
        request_id=request_id,
        active_generation_id=callback_data.generation_id,
        active_photo_message_id=sent_photo_msg.message_id,
        active_control_message_id=new_control_message.message_id,
        session_context=session_context.value, # <-- Set the restored context
        continue_key=continue_key,
        parent_descriptions=context_from_db.context.parent_descriptions,
        child_description=context_from_db.context.child_description.model_dump() if context_from_db.context.child_description else None,
        root_request_id=root_request_id,
    )
    log.info("Successfully reactivated generation.", new_active_msg_id=new_control_message.message_id)


# --- ROUTER REGISTRATION ---

@router.callback_query(ReturnToMainMenu.filter(), StateFilter("*"))
async def return_to_main_menu(
    cb: CallbackQuery, callback_data: ReturnToMainMenu, state: FSMContext,
    db_pool: asyncpg.Pool, business_logger: structlog.typing.FilteringBoundLogger,
):
    with suppress(TelegramBadRequest): await cb.answer()
    asyncio.create_task(_process_return_to_main_menu_async(cb, callback_data, state, db_pool, business_logger))


@router.callback_query(ContinueEditingCallback.filter(), StateFilter("*"))
async def continue_editing(
    cb: CallbackQuery, callback_data: ContinueEditingCallback, state: FSMContext,
    cache_pool: Redis, db_pool: asyncpg.Pool, business_logger: structlog.typing.FilteringBoundLogger
):
    with suppress(TelegramBadRequest): await cb.answer()
    asyncio.create_task(_process_continue_editing_async(cb, callback_data, state, cache_pool, db_pool, business_logger))


@router.callback_query(GetHdCallback.filter(), StateFilter("*"))
async def process_hd_request(
    cb: CallbackQuery, callback_data: GetHdCallback, state: FSMContext,
    cache_pool: Redis, db_pool: asyncpg.Pool, business_logger: structlog.typing.FilteringBoundLogger,
):
    with suppress(TelegramBadRequest): await cb.answer()
    asyncio.create_task(_process_hd_request_async(cb, callback_data, state, cache_pool, db_pool, business_logger))


@router.callback_query(CreateGroupPhotoCallback.filter(), StateFilter("*"))
async def process_create_group_photo(
    cb: CallbackQuery, callback_data: CreateGroupPhotoCallback, state: FSMContext,
    cache_pool: Redis, db_pool: asyncpg.Pool, business_logger: structlog.typing.FilteringBoundLogger,
):
    with suppress(TelegramBadRequest): await cb.answer()
    asyncio.create_task(_process_create_group_photo_async(
        cb, callback_data, state, cache_pool, db_pool, business_logger
    ))


@router.callback_query(F.data == "start_new", StateFilter("*"))
async def start_new_generation(
    callback: CallbackQuery,
    state: FSMContext,
    bot: Bot,
    db_pool: asyncpg.Pool,
    business_logger: structlog.typing.FilteringBoundLogger
):
    with suppress(TelegramBadRequest): await callback.answer()
    asyncio.create_task(_process_start_new_generation_async(
        callback, state, bot, db_pool, business_logger
    ))

@router.callback_query(RetryGenerationCallback.filter(), StateFilter("*"))
async def process_retry_generation(
    cb: CallbackQuery, callback_data: RetryGenerationCallback, state: FSMContext,
    db_pool: asyncpg.Pool, business_logger: structlog.typing.FilteringBoundLogger
):
    with suppress(TelegramBadRequest): await cb.answer()
    asyncio.create_task(_process_retry_generation_async(cb, callback_data, state, db_pool, business_logger))


@router.callback_query(EditChildParamsCallback.filter(), StateFilter("*"))
async def process_edit_child_params(
    cb: CallbackQuery, callback_data: EditChildParamsCallback, state: FSMContext,
    db_pool: asyncpg.Pool, business_logger: structlog.typing.FilteringBoundLogger
):
    with suppress(TelegramBadRequest): await cb.answer()
    asyncio.create_task(_process_edit_child_params_async(cb, callback_data, state, db_pool, business_logger))


async def _load_original_request(db_pool, request_id, logger):
    db = PostgresConnection(db_pool, logger=logger)
    original_request = await generations_repo.get_request_details_with_sources(db, request_id)
    return original_request if original_request and original_request.get("source_images") else None


@router.callback_query(ReturnToGenerationCallback.filter(), StateFilter("*"))
async def reactivate_generation(
    cb: CallbackQuery,
    callback_data: ReturnToGenerationCallback,
    state: FSMContext,
    bot: Bot,
    db_pool: asyncpg.Pool,
    cache_pool: Redis,
    business_logger: structlog.typing.FilteringBoundLogger,
):
    """Handles the press of the 'Return to this Generation' button."""
    with suppress(TelegramBadRequest):
        await cb.answer()
    asyncio.create_task(_process_reactivate_generation_async(
        cb, callback_data, state, bot, db_pool, cache_pool, business_logger
    ))
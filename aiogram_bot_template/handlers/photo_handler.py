# aiogram_bot_template/handlers/photo_handler.py
import asyncio
import asyncpg
import structlog
from pathlib import Path
from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, PhotoSize, FSInputFile
from aiogram.utils.i18n import gettext as _
from redis.asyncio import Redis
from typing import Dict, List, Tuple, Optional, Any
from contextlib import suppress
from aiogram.exceptions import TelegramBadRequest

from aiogram_bot_template.data.constants import GenerationType, ImageRole
from aiogram_bot_template.db.db_api.storages import PostgresConnection
from aiogram_bot_template.db.repo import generations as generations_repo
from aiogram_bot_template.services import image_cache, photo_processing
from aiogram_bot_template.states.user import Generation
from aiogram_bot_template.keyboards.inline.gender import gender_kb
from aiogram_bot_template.services.pipelines.pair_photo_pipeline import styles as pair_styles
from aiogram_bot_template.keyboards.inline.style_selection import get_style_selection_button_kb
from aiogram_bot_template.services.photo_processing_manager import PhotoProcessingManager

router = Router(name="photo-handler")

user_batch_tasks: Dict[int, asyncio.Task] = {}
user_batch_cache: Dict[int, List[Message]] = {}
DEBOUNCE_DELAY_SECONDS = 2.5
MIN_PHOTOS_PER_PARENT = 4


async def send_style_previews(
    bot: Bot,
    chat_id: int,
    state: FSMContext,
    logger: structlog.typing.FilteringBoundLogger,
    styles_registry: Dict[str, Any]
) -> None:
    """
    Sends a series of messages, each with a style preview image and a selection button.
    Stores the message IDs in FSM context for later cleanup.
    """
    assets_path = Path(__file__).parent.parent / "assets" / "style_previews"
    sent_message_ids = []

    for style_id, style_info in styles_registry.items():
        image_path = assets_path / style_info["preview_image"]
        if not image_path.exists():
            logger.warning("Style preview image not found", path=str(image_path))
            continue

        photo = FSInputFile(image_path)
        caption = _("Style Preview: <b>{style_name}</b>").format(style_name=_(style_info["name"]))
        
        try:
            msg = await bot.send_photo(
                chat_id=chat_id,
                photo=photo,
                caption=caption,
                reply_markup=get_style_selection_button_kb(style_id=style_id)
            )
            sent_message_ids.append(msg.message_id)
        except TelegramBadRequest as e:
            logger.error("Failed to send style preview photo", style_id=style_id, error=e)

    if sent_message_ids:
        cta_msg = await bot.send_message(
            chat_id=chat_id,
            text=_("⬆️ Please select a style by clicking a button below one of the images.")
        )
        sent_message_ids.append(cta_msg.message_id)

    data = await state.get_data()
    existing_ids = data.get("style_preview_message_ids", [])
    await state.update_data(style_preview_message_ids=existing_ids + sent_message_ids)


async def proceed_to_child_params(message: Message, state: FSMContext) -> None:
    """
    After collecting photos for child generation, starts the parameter
    selection flow by asking for the gender.
    """
    await state.set_state(Generation.choosing_child_gender)
    await message.answer(
        _("Excellent! I have enough high-quality photos for both parents. "
          "Now, let's imagine your future child.\n\n"
          "First, what is the desired gender?"),
        reply_markup=gender_kb()
    )


async def proceed_to_style_selection(
    message: Message,
    state: FSMContext,
    bot: Bot,
    business_logger: structlog.typing.FilteringBoundLogger
) -> None:
    """
    After collecting photos for a pair portrait, proceeds to style selection.
    This function NO LONGER interacts with the database.
    """
    await state.set_state(Generation.choosing_pair_photo_style)
    
    sent_msg = await message.answer(
        _("Perfect, all photos are collected! Now for the fun part.")
    )
    await state.update_data(style_preview_message_ids=[sent_msg.message_id])
    
    await send_style_previews(
        bot=bot,
        chat_id=message.chat.id,
        state=state,
        logger=business_logger,
        styles_registry=pair_styles.STYLES
    )


async def _download_one_photo(
    photo: PhotoSize, bot: Bot
) -> Optional[Tuple[bytes, str, str]]:
    """
    Correctly downloads a single photo using the get_file -> download_file sequence.
    """
    try:
        file_info = await bot.get_file(photo.file_id)
        if not file_info.file_path: return None
        file_io = await bot.download_file(file_info.file_path)
        if not file_io: return None
        return (file_io.read(), photo.file_unique_id, photo.file_id)
    except Exception:
        structlog.get_logger(__name__).warning("Failed to download one photo", file_id=photo.file_id)
        return None

async def process_photo_batch(
    messages: List[Message], state: FSMContext, bot: Bot, db_pool: asyncpg.Pool, cache_pool: Redis, photo_manager: PhotoProcessingManager
):
    """
    Handles processing a batch of photos, validation, collage creation, and routing to the next step.
    This now offloads heavy work to the PhotoProcessingManager.
    """
    message = messages[0]
    user_id = message.from_user.id
    log = structlog.get_logger(__name__).bind(user_id=user_id)
    status_msg = await message.answer(_("Analyzing your photos... ⏳"))
    db = PostgresConnection(db_pool, logger=log)

    try:
        uid_to_msg_id = {
            max(msg.photo, key=lambda p: p.width * p.height).file_unique_id: msg.message_id
            for msg in messages if msg.photo
        }

        download_tasks = [
            _download_one_photo(max(msg.photo, key=lambda p: p.width * p.height), bot)
            for msg in messages if msg.photo
        ]
        downloaded_results = await asyncio.gather(*download_tasks)
        photo_inputs = [res for res in downloaded_results if res is not None]

        if not photo_inputs:
            await status_msg.edit_text(_("I couldn't process these photos. Please try sending them again."))
            return
        
        processed_photos_info = await photo_manager.process_photo_batch(photo_inputs)
        
        if not processed_photos_info:
            rejection_text = _(
                "Unfortunately, none of the photos you sent were suitable.\n\n"
                "I'm looking for photos with:\n"
                "• <b>Exactly one person</b> in the frame.\n"
                "• A clear, relatively large view of the face.\n"
                "• No major obstructions like sunglasses or hands.\n\n"
                "Please try sending another photo or two. Thank you! 😊"
            )
            await status_msg.edit_text(rejection_text)
            return
        
        await asyncio.gather(*(
            image_cache.cache_image_bytes(uid, p_bytes, "image/jpeg", cache_pool)
            for uid, _, p_bytes in processed_photos_info
        ))

        data = await state.get_data()
        photos_collected = data.get("photos_collected", [])
        
        mom_photos_count = sum(1 for p in photos_collected if p.get("role") == ImageRole.MOTHER.value)
        current_role = ImageRole.MOTHER if mom_photos_count < MIN_PHOTOS_PER_PARENT else ImageRole.FATHER

        photos_collected.extend([
            {
                "file_id": file_id,
                "file_unique_id": uid,
                "role": current_role.value,
                "message_id": uid_to_msg_id.get(uid)
            }
            for uid, file_id, _ in processed_photos_info
        ])
        await state.update_data(photos_collected=photos_collected)
        
        log.info("Added new valid & processed photos to state", role=current_role.value, count=len(processed_photos_info))

        data = await state.get_data()
        mom_photos = [p for p in photos_collected if p['role'] == ImageRole.MOTHER.value]
        dad_photos = [p for p in photos_collected if p['role'] == ImageRole.FATHER.value]
        
        parent_to_sort = None
        if len(mom_photos) >= MIN_PHOTOS_PER_PARENT and not data.get("mom_photos_sorted"):
            parent_to_sort = (mom_photos, ImageRole.MOTHER.value, "mom_photos_sorted")
            await status_msg.edit_text(_("Great! Checking consistency of photos... ✨"))
        elif len(dad_photos) >= MIN_PHOTOS_PER_PARENT and not data.get("dad_photos_sorted"):
            parent_to_sort = (dad_photos, ImageRole.FATHER.value, "dad_photos_sorted")
            await status_msg.edit_text(_("Perfect! Checking consistency of photos... ✨"))
        
        if parent_to_sort:
            photos_list, role_str, state_flag = parent_to_sort
            
            request_id = data.get("request_id")
            if not request_id:
                draft = generations_repo.GenerationRequestDraft(
                    user_id=user_id, status="photos_collected", source_images=[]
                )
                request_id = await generations_repo.create_generation_request(db, draft)
                await state.update_data(request_id=request_id)
                log.info("Created new GenerationRequest in DB.", request_id=request_id)

            bytes_tasks = [image_cache.get_cached_image_bytes(p['file_unique_id'], cache_pool) for p in photos_list]
            cached_results = await asyncio.gather(*bytes_tasks)
            photos_with_bytes = [{**photos_list[i], 'bytes': b} for i, (b, _) in enumerate(cached_results) if b]
            
            best_photos = await photo_manager.sort_and_filter_by_identity(photos_with_bytes, target_count=MIN_PHOTOS_PER_PARENT)
            
            best_photos_bytes = [p['bytes'] for p in best_photos]
            collage_bytes = await photo_manager.create_portrait_collage(best_photos_bytes)
            
            collage_uid = f"collage_{role_str}_proc_{request_id}"
            await image_cache.cache_image_bytes(collage_uid, collage_bytes, "image/jpeg", cache_pool)
            
            state_update_payload = {state_flag: True, f"{role_str}_collage_uid": collage_uid}
            await state.update_data(**state_update_payload)
            log.info("Created and cached parent collage.", role=role_str, collage_uid=collage_uid)

            for p in best_photos: p.pop('bytes', None)
            other_parent_photos = [p for p in photos_collected if p['role'] != role_str]
            updated_photos_collected = other_parent_photos + best_photos
            
            await state.update_data(photos_collected=updated_photos_collected)
            log.info("Filtered and sorted photos for parent.", role=role_str, final_count=len(best_photos))

            source_images_dto = [(p["file_unique_id"], p["file_id"], p["role"]) for p in best_photos]
            sql_insert_image = """
                INSERT INTO generation_source_images (request_id, file_unique_id, file_id, role)
                VALUES ($1, $2, $3, $4) ON CONFLICT DO NOTHING;
            """
            images_data = [(request_id, uid, fid, role) for uid, fid, role in source_images_dto]
            await db.execute(sql_insert_image, images_data)
            log.info("Saved parent source images to DB.", role=role_str, count=len(images_data))


        await status_msg.delete()

        final_data = await state.get_data()
        final_photos = final_data.get("photos_collected", [])
        final_mom_count = sum(1 for p in final_photos if p['role'] == ImageRole.MOTHER.value)
        final_dad_count = sum(1 for p in final_photos if p['role'] == ImageRole.FATHER.value)

        if final_mom_count >= MIN_PHOTOS_PER_PARENT and final_dad_count >= MIN_PHOTOS_PER_PARENT:
            generation_type = GenerationType(final_data["generation_type"])
            if generation_type == GenerationType.CHILD_GENERATION:
                await proceed_to_child_params(message, state)
            elif generation_type == GenerationType.PAIR_PHOTO:
                await proceed_to_style_selection(message, state, bot, log)
            else:
                log.error("Unhandled generation type after photo collection", type=generation_type)
                await message.answer(_("An unexpected error occurred. Please /start over."))
        elif final_mom_count < MIN_PHOTOS_PER_PARENT:
            person_name = _("the Mother") if final_data["generation_type"] == GenerationType.CHILD_GENERATION.value else _("the first person")
            next_prompt = _("Got it! I now have <b>{count}/{min_count}</b> good photos of {person}. Please send a few more photos of them.").format(count=final_mom_count, min_count=MIN_PHOTOS_PER_PARENT, person=person_name)
            await message.answer(next_prompt)
        else:
            person_name = _("the Dad") if final_data["generation_type"] == GenerationType.CHILD_GENERATION.value else _("the second person")
            is_first_request = (final_dad_count == 0)
            if is_first_request:
                next_prompt = _("Perfect, that's enough for the first person! Now I need photos of the second person. Please send at least {min_count} high-quality photos of them.").format(min_count=MIN_PHOTOS_PER_PARENT)
            else:
                next_prompt = _("Thanks! I now have <b>{count}/{min_count}</b> good photos of {person}. Please send a few more of them.").format(count=final_dad_count, min_count=MIN_PHOTOS_PER_PARENT, person=person_name)
            await message.answer(next_prompt)

    except Exception as e:
        log.error("Error processing photo batch", exc_info=e)
        with suppress(TelegramBadRequest):
            await status_msg.edit_text(_("I ran into an issue. Please try sending another photo or use /cancel to start over."))

async def delayed_batch_processor(
    user_id: int, state: FSMContext, bot: Bot, db_pool: asyncpg.Pool, cache_pool: Redis, photo_manager: PhotoProcessingManager
):
    """
    Waits for the debounce delay, then processes all cached photos for the user.
    """
    await asyncio.sleep(DEBOUNCE_DELAY_SECONDS)
    messages = user_batch_cache.pop(user_id, [])
    user_batch_tasks.pop(user_id, None)
    
    if messages:
        messages.sort(key=lambda m: m.message_id)
        await process_photo_batch(messages, state, bot, db_pool, cache_pool, photo_manager)

@router.message(Generation.collecting_photos, F.photo)
async def process_photo_input(
    message: Message, state: FSMContext, bot: Bot, db_pool: asyncpg.Pool, cache_pool: Redis, photo_manager: PhotoProcessingManager
) -> None:
    """
    Catches all incoming photos and uses a debounce mechanism to group them.
    The photo_manager is now passed in from the dispatcher.
    """
    if not message.from_user: return
    user_id = message.from_user.id

    if user_id in user_batch_tasks:
        user_batch_tasks[user_id].cancel()

    if user_id not in user_batch_cache:
        user_batch_cache[user_id] = []
    
    if not any(m.message_id == message.message_id for m in user_batch_cache[user_id]):
        user_batch_cache[user_id].append(message)
    
    user_batch_tasks[user_id] = asyncio.create_task(
        delayed_batch_processor(user_id, state, bot, db_pool, cache_pool, photo_manager)
    )
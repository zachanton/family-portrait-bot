# aiogram_bot_template/handlers/photo_handler.py
import asyncio
import structlog
from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, PhotoSize
from aiogram.utils.i18n import gettext as _
from redis.asyncio import Redis
from typing import Dict, List, Tuple, Optional

from aiogram_bot_template.data.constants import ImageRole
from aiogram_bot_template.services import image_cache, similarity_scorer
from aiogram_bot_template.states.user import Generation
from aiogram_bot_template.keyboards.inline.gender import gender_kb

router = Router(name="photo-handler")

# --- NEW: Debounce mechanism to handle bursts of photos ---
# Stores the asyncio.Task for a user's delayed photo processing
user_batch_tasks: Dict[int, asyncio.Task] = {}
# Caches incoming photo messages for a user before processing
user_batch_cache: Dict[int, List[Message]] = {}
DEBOUNCE_DELAY_SECONDS = 2.5

MIN_PHOTOS_PER_PARENT = 4

# --- Helper functions (proceed_to_child_params, _download_one_photo) remain unchanged ---
async def proceed_to_child_params(message: Message, state: FSMContext) -> None:
    """
    After collecting enough photos for both parents, starts the child parameter
    selection flow by asking for the gender.
    """
    await state.set_state(Generation.choosing_child_gender)
    await message.answer(
        _("Excellent! I have enough high-quality photos for both parents. "
          "Now, let's imagine your future child.\n\n"
          "First, what is the desired gender?"),
        reply_markup=gender_kb()
    )

async def _download_one_photo(
    photo: PhotoSize, bot: Bot
) -> Optional[Tuple[bytes, str, str]]:
    """
    Correctly downloads a single photo using the get_file -> download_file sequence.
    
    Returns:
        A tuple of (image_bytes, file_unique_id, file_id) or None on failure.
    """
    try:
        file_info = await bot.get_file(photo.file_id)
        if not file_info.file_path:
            return None
        
        file_io = await bot.download_file(file_info.file_path)
        if not file_io:
            return None
            
        return (file_io.read(), photo.file_unique_id, photo.file_id)
    except Exception:
        structlog.get_logger(__name__).warning("Failed to download one photo", file_id=photo.file_id)
        return None

async def process_photo_batch(
    messages: List[Message], state: FSMContext, bot: Bot, cache_pool: Redis
):
    """
    Handles processing a batch of photos, including validation, preprocessing,
    and a final identity-based sorting and filtering step.
    """
    message = messages[0]
    log = structlog.get_logger(__name__)
    status_msg = await message.answer(_("Analyzing your photos... ⏳"))

    try:
        download_tasks = [
            _download_one_photo(max(msg.photo, key=lambda p: p.width * p.height), bot)
            for msg in messages if msg.photo
        ]
        downloaded_results = await asyncio.gather(*download_tasks)
        photo_inputs = [res for res in downloaded_results if res is not None]

        if not photo_inputs:
            await status_msg.edit_text(_("I couldn't process these photos. Please try sending them again."))
            return

        processed_photos_info = await similarity_scorer.select_best_photos_and_process(photo_inputs)
        
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
            {"file_id": file_id, "file_unique_id": uid, "role": current_role.value}
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
            
            bytes_tasks = [image_cache.get_cached_image_bytes(p['file_unique_id'], cache_pool) for p in photos_list]
            cached_results = await asyncio.gather(*bytes_tasks)

            photos_with_bytes = [
                {**photos_list[i], 'bytes': b} for i, (b, _) in enumerate(cached_results) if b
            ]
            
            # --- UPDATED CALL: target_count is now our required number (4) ---
            best_photos = await similarity_scorer.sort_and_filter_by_identity(
                photos_with_bytes, target_count=MIN_PHOTOS_PER_PARENT
            )

            for p in best_photos: p.pop('bytes', None)

            other_parent_photos = [p for p in photos_collected if p['role'] != role_str]
            updated_photos_collected = other_parent_photos + best_photos
            
            await state.update_data(photos_collected=updated_photos_collected, **{state_flag: True})
            log.info("Filtered and sorted photos for parent.", role=role_str, final_count=len(best_photos))

        await status_msg.delete()

        final_data = await state.get_data()
        final_photos = final_data.get("photos_collected", [])
        final_mom_count = sum(1 for p in final_photos if p['role'] == ImageRole.MOTHER.value)
        final_dad_count = sum(1 for p in final_photos if p['role'] == ImageRole.FATHER.value)

        if final_mom_count >= MIN_PHOTOS_PER_PARENT and final_dad_count >= MIN_PHOTOS_PER_PARENT:
            await proceed_to_child_params(message, state)
        elif final_mom_count < MIN_PHOTOS_PER_PARENT:
            # --- UPDATED TEXT ---
            next_prompt = _(
                "Got it! I now have <b>{count}/{min_count}</b> good photos of the Mom. "
                "Please send a few more photos of her."
            ).format(count=final_mom_count, min_count=MIN_PHOTOS_PER_PARENT)
            await message.answer(next_prompt)
        else:
            is_first_dad_request = (final_dad_count == 0)
            if is_first_dad_request:
                next_prompt = _(
                    "Perfect, that's enough for the Mom! Now I need photos of the Dad. "
                    "Please send at least {min_count} high-quality photos of him."
                ).format(min_count=MIN_PHOTOS_PER_PARENT)
            else:
                next_prompt = _(
                    "Thanks! I now have <b>{count}/{min_count}</b> good photos of the Dad. "
                    "Please send a few more of him."
                ).format(count=final_dad_count, min_count=MIN_PHOTOS_PER_PARENT)
            await message.answer(next_prompt)

    except Exception as e:
        log.error("Error processing photo batch", exc_info=e)
        await status_msg.edit_text(_("I ran into an issue. Please try sending another photo or use /cancel to start over."))


async def delayed_batch_processor(
    user_id: int, state: FSMContext, bot: Bot, cache_pool: Redis
):
    """
    Waits for the debounce delay, then processes all cached photos for the user.
    This function runs as a separate, non-blocking asyncio task.
    """
    await asyncio.sleep(DEBOUNCE_DELAY_SECONDS)

    # Retrieve all messages for this user's burst from the cache
    messages = user_batch_cache.pop(user_id, [])
    # Clean up the task entry
    user_batch_tasks.pop(user_id, None)
    
    if messages:
        # Sort messages by ID to process them in the order they were sent
        messages.sort(key=lambda m: m.message_id)
        await process_photo_batch(messages, state, bot, cache_pool)


# --- REWRITTEN: The main handler is now much simpler ---
@router.message(Generation.collecting_photos, F.photo)
async def process_photo_input(
    message: Message, state: FSMContext, bot: Bot, cache_pool: Redis
) -> None:
    """
    Catches all incoming photos (single or album) and uses a debounce
    mechanism to group them into a single processing batch.
    """
    if not message.from_user:
        return
        
    user_id = message.from_user.id

    # If a processing task is already scheduled for this user, cancel it.
    # This is the "reset the timer" part of debouncing.
    if user_id in user_batch_tasks:
        user_batch_tasks[user_id].cancel()

    # Add the new message to the user's batch cache.
    if user_id not in user_batch_cache:
        user_batch_cache[user_id] = []
    
    # We must handle albums correctly by finding all related messages.
    # The debounce handler will receive messages one by one. If they have a
    # media_group_id, we add them to the cache. We need to avoid duplicates.
    # A simple check on message_id is sufficient.
    
    # Check if this message is already in the cache (can happen with albums)
    if not any(m.message_id == message.message_id for m in user_batch_cache[user_id]):
        user_batch_cache[user_id].append(message)
    
    # Schedule a new delayed processor task.
    user_batch_tasks[user_id] = asyncio.create_task(
        delayed_batch_processor(user_id, state, bot, cache_pool)
    )
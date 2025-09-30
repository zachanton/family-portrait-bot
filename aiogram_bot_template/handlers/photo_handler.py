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

album_message_cache: Dict[str, List[Message]] = {}
album_tasks: Dict[str, asyncio.Task] = {}

# The minimum number of high-quality photos required for EACH parent.
MIN_PHOTOS_PER_PARENT = 3

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
    Handles the logic for processing a batch of photos.
    It scores them, adds valid ones to the state, and iteratively asks for more
    until the minimum count per parent is reached.
    """
    message = messages[0]
    log = structlog.get_logger(__name__)
    status_msg = await message.answer(_("Analyzing your photo(s)... ⏳"))

    try:
        # Step 1: Download all photos from the message batch
        download_tasks = []
        for msg in messages:
            if msg.photo:
                photo = max(msg.photo, key=lambda p: p.width * p.height)
                download_tasks.append(_download_one_photo(photo, bot))

        downloaded_results = await asyncio.gather(*download_tasks)
        photo_inputs = [res for res in downloaded_results if res is not None]

        if not photo_inputs:
            await status_msg.edit_text(_("I couldn't process these photos. Please try sending them again."))
            return

        # Step 2: Score, align, and filter the downloaded photos
        best_photos_info = await similarity_scorer.select_best_photos(photo_inputs)
        
        if not best_photos_info:
            rejection_text = _(
                "Unfortunately, none of the photos you sent were suitable.\n\n"
                "I'm looking for photos with:\n"
                "• <b>Exactly one person</b> in the frame.\n"
                "• A clear view of the face (<b>not the back of the head</b>).\n"
                "• No major obstructions like sunglasses or hands covering the face.\n\n"
                "Please try sending another photo or two. Thank you! 😊"
            )
            await status_msg.edit_text(rejection_text)
            return
        
        # Step 3: Cache all newly selected and aligned images
        await asyncio.gather(*(
            image_cache.cache_image_bytes(unique_id, photo_bytes, "image/jpeg", cache_pool)
            for unique_id, file_id, photo_bytes in best_photos_info
        ))

        await status_msg.delete()
        
        # Step 4: Determine current role and update the state
        data = await state.get_data()
        photos_collected = data.get("photos_collected", [])
        
        mom_photos_count = sum(1 for p in photos_collected if p.get("role") == ImageRole.MOTHER.value)
        
        current_role = ImageRole.MOTHER if mom_photos_count < MIN_PHOTOS_PER_PARENT else ImageRole.FATHER

        photos_collected.extend([
            {"file_id": file_id, "file_unique_id": unique_id, "role": current_role.value}
            for unique_id, file_id, _ in best_photos_info
        ])
        await state.update_data(photos_collected=photos_collected)
        
        log.info(
            "Added new valid photos to state",
            role=current_role.value,
            count=len(best_photos_info)
        )

        # Step 5: Check the counts and decide the next action
        mom_photos_count = sum(1 for p in photos_collected if p.get("role") == ImageRole.MOTHER.value)
        dad_photos_count = sum(1 for p in photos_collected if p.get("role") == ImageRole.FATHER.value)

        if mom_photos_count >= MIN_PHOTOS_PER_PARENT and dad_photos_count >= MIN_PHOTOS_PER_PARENT:
            await proceed_to_child_params(message, state)
        elif mom_photos_count < MIN_PHOTOS_PER_PARENT:
            next_prompt = _(
                "Got it! I now have <b>{count}/{min_count}</b> good photos of the Mom. "
                "Please send a few more photos of her."
            ).format(count=mom_photos_count, min_count=MIN_PHOTOS_PER_PARENT)
            await message.answer(next_prompt)
        else: # Mom's photos are done, collecting for Dad
            # Check if this is the very first time we're asking for Dad's photos
            is_first_dad_request = (dad_photos_count == 0)
            
            if is_first_dad_request:
                next_prompt = _(
                    "Perfect, that's enough for the Mom! Now I need photos of the Dad. "
                    "Please send at least {min_count} high-quality photos of him."
                ).format(min_count=MIN_PHOTOS_PER_PARENT)
            else:
                next_prompt = _(
                    "Thanks! I now have <b>{count}/{min_count}</b> good photos of the Dad. "
                    "Please send a few more of him."
                ).format(count=dad_photos_count, min_count=MIN_PHOTOS_PER_PARENT)
            await message.answer(next_prompt)

    except Exception as e:
        log.error("Error processing photo batch", exc_info=e)
        await status_msg.edit_text(_("I ran into an issue. Please try sending another photo or use /cancel to start over."))


@router.message(Generation.collecting_photos, F.photo)
async def process_photo_input(
    message: Message, state: FSMContext, bot: Bot, cache_pool: Redis
) -> None:
    """
    Catches incoming photos, groups them by media_group_id using an in-memory
    cache, and schedules a delayed task to process the complete album.
    """
    media_group_id = message.media_group_id

    if not media_group_id:
        # If it's a single photo, process it immediately.
        await process_photo_batch([message], state, bot, cache_pool)
        return

    media_group_id_str = str(media_group_id)

    # If a task for this album already exists, cancel it to reset the timer.
    if media_group_id_str in album_tasks:
        album_tasks[media_group_id_str].cancel()

    # Add the new message to the cache for this album.
    if media_group_id_str not in album_message_cache:
        album_message_cache[media_group_id_str] = []
    
    album_message_cache[media_group_id_str].append(message)
    
    # Schedule a new delayed processor.
    album_tasks[media_group_id_str] = asyncio.create_task(
        delayed_album_processor(media_group_id_str, state, bot, cache_pool)
    )

async def delayed_album_processor(
    media_group_id: str, state: FSMContext, bot: Bot, cache_pool: Redis
):
    """
    Waits a short moment to allow all photos in an album to arrive,
    then triggers the main processing function and cleans up the cache.
    """
    await asyncio.sleep(1.0)  # Wait for 1 second

    # Retrieve all messages for this album from the cache.
    messages = album_message_cache.pop(media_group_id, [])
    
    if messages:
        # Sort messages by ID to process them in the order they were sent.
        messages.sort(key=lambda m: m.message_id)
        await process_photo_batch(messages, state, bot, cache_pool)
    
    # Clean up the task entry.
    if media_group_id in album_tasks:
        del album_tasks[media_group_id]
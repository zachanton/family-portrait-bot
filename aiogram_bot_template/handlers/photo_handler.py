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

async def proceed_to_child_params(message: Message, state: FSMContext) -> None:
    """
    After collecting photos, starts the child parameter selection flow
    by asking for the gender.
    """
    await state.set_state(Generation.choosing_child_gender)
    await message.answer(
        _("Great, I have both sets of photos! Now, let's imagine your future child.\n\n"
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
    Handles the logic for processing a single photo or an album of photos.
    It selects the best photos and updates the state.
    """
    message = messages[0]
    status_msg = await message.answer(_("Analyzing your photo(s)... ⏳"))

    try:
        download_tasks = []
        for msg in messages:
            if msg.photo:
                # Use the highest resolution photo available
                photo = max(msg.photo, key=lambda p: p.width * p.height)
                download_tasks.append(_download_one_photo(photo, bot))

        downloaded_results = await asyncio.gather(*download_tasks)
        photo_inputs = [res for res in downloaded_results if res is not None]

        if not photo_inputs:
            await status_msg.edit_text(_("I couldn't process the photos. Please try sending them again."))
            return

        # --- MODIFICATION: Call select_best_photos without num_to_select ---
        best_photos_info = await similarity_scorer.select_best_photos(photo_inputs)
        
        if not best_photos_info:
            rejection_text = _(
                "Unfortunately, I couldn't find a suitable photo among the ones you sent.\n\n"
                "To get the best possible result, I need photos that meet a few criteria:\n"
                "• <b>Only one person</b> in the frame.\n"
                "• The face is <b>clearly visible, facing forward</b>, and not tilted.\n"
                "• No glasses, hats, or other objects <b>covering the face</b>.\n"
                "• The photo is <b>sharp and not blurry</b>.\n\n"
                "Please try sending another photo(s). Thank you! 😊"
            )
            await status_msg.edit_text(rejection_text)
            return
        
        # Cache all selected images
        cache_tasks = []
        for unique_id, a, photo_bytes in best_photos_info:
            cache_tasks.append(
                image_cache.cache_image_bytes(unique_id, photo_bytes, "image/jpeg", cache_pool)
            )
        await asyncio.gather(*cache_tasks)

        await status_msg.delete()
        
        data = await state.get_data()
        photos_collected = data.get("photos_collected", [])
        
        # Determine if we are collecting for Mom or Dad
        # A simple way to check is by counting existing unique roles
        roles_present = {p.get("role") for p in photos_collected if p.get("role")}
        
        if ImageRole.MOTHER.value not in roles_present:
            current_role = ImageRole.MOTHER
            next_prompt = _("Perfect! Now, please send one or more photos of the Dad.")
        elif ImageRole.FATHER.value not in roles_present:
            current_role = ImageRole.FATHER
            # If we've just collected for Dad, then proceed to child params
            next_prompt = None # No prompt needed, will proceed to child params
        else:
            # Should not happen if flow is sequential, but for safety
            current_role = ImageRole.MOTHER # Fallback
            next_prompt = _("Unexpected state. Please send one or more photos of the Mom.")


        # --- MODIFICATION: Store a list of photos for the current role ---
        selected_photos_dto = [
            {
                "file_id": file_id,
                "file_unique_id": unique_id,
                "role": current_role.value
            }
            for unique_id, file_id, a in best_photos_info
        ]

        photos_collected.extend(selected_photos_dto)
        await state.update_data(photos_collected=photos_collected)

        # Check if we have photos for both parents
        final_roles_present = {p.get("role") for p in photos_collected if p.get("role")}

        if ImageRole.MOTHER.value in final_roles_present and ImageRole.FATHER.value in final_roles_present:
            await proceed_to_child_params(message, state)
        elif next_prompt: # If we need more photos for the other parent
            await message.answer(next_prompt)


    except Exception as e:
        structlog.get_logger(__name__).error("Error processing photo batch", exc_info=e)
        await status_msg.edit_text(_("I couldn't process these images. Please try another one or /cancel."))


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
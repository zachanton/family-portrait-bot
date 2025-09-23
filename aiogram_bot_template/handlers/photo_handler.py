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
        _("Great, I have both photos! Now, let's imagine your future child.\n\n"
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
    It selects the best photo and updates the state.
    """
    message = messages[0]
    status_msg = await message.answer(_("Analyzing your photo(s)... ⏳"))

    try:
        download_tasks = []
        for msg in messages:
            if msg.photo:
                photo = msg.photo[-1]
                download_tasks.append(_download_one_photo(photo, bot))

        downloaded_results = await asyncio.gather(*download_tasks)
        photo_inputs = [res for res in downloaded_results if res is not None]

        if not photo_inputs:
            await status_msg.edit_text(_("I couldn't process the photos. Please try sending them again."))
            return

        best_photo_info = await similarity_scorer.select_best_photo(photo_inputs)
        
        if not best_photo_info:
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
        
        best_unique_id, best_file_id, best_photo_bytes = best_photo_info

        await image_cache.cache_image_bytes(best_unique_id, best_photo_bytes, "image/jpeg", cache_pool)

        await status_msg.delete()
        
        data = await state.get_data()
        photos_collected = data.get("photos_collected", [])
        
        current_role = ImageRole.MOTHER if not photos_collected else ImageRole.FATHER

        photos_collected.append({
            "file_id": best_file_id,
            "file_unique_id": best_unique_id,
            "role": current_role.value
        })
        await state.update_data(photos_collected=photos_collected)

        if len(photos_collected) < 2:
            await message.answer(_("Perfect! Now, please send one or more photos of the Dad."))
        else:
            await proceed_to_child_params(message, state)

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
        await process_photo_batch([message], state, bot, cache_pool)
        return

    media_group_id_str = str(media_group_id)

    if media_group_id_str in album_tasks:
        album_tasks[media_group_id_str].cancel()

    if media_group_id_str not in album_message_cache:
        album_message_cache[media_group_id_str] = []
    
    album_message_cache[media_group_id_str].append(message)
    
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
    await asyncio.sleep(1.0)

    messages = album_message_cache.pop(media_group_id, [])
    
    if messages:
        messages.sort(key=lambda m: m.message_id)
        await process_photo_batch(messages, state, bot, cache_pool)
    
    if media_group_id in album_tasks:
        del album_tasks[media_group_id]
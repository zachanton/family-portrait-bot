# aiogram_bot_template/handlers/photo_handler.py
import asyncpg
import structlog
from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram.utils.i18n import gettext as _
from redis.asyncio import Redis

from aiogram_bot_template.data.constants import ImageRole
from aiogram_bot_template.services import image_cache
from aiogram_bot_template.states.user import Generation
# --- NEW: Import the new keyboard ---
from aiogram_bot_template.keyboards.inline.gender import gender_kb

router = Router(name="photo-handler")

# --- REFACTORED: This function now transitions to the child parameter selection flow ---
async def proceed_to_child_params(message: Message, state: FSMContext) -> None:
    """
    After collecting photos, starts the child parameter selection flow
    by asking for the gender.
    """
    await state.set_state(Generation.choosing_child_gender)
    await message.answer(
        _("Great, I have both photos! Now, let's define your future child.\n\n"
          "First, choose the desired gender:"),
        reply_markup=gender_kb()
    )


@router.message(Generation.collecting_photos, F.photo)
async def process_photo_input(
    message: Message, state: FSMContext, bot: Bot, cache_pool: Redis
) -> None:
    """Handles receiving photos one by one."""
    photo = message.photo[-1]
    status_msg = await message.answer(_("Processing your photo... ⏳"))

    try:
        file_info = await bot.get_file(photo.file_id)
        if not file_info.file_path:
            await status_msg.edit_text(_("I couldn't get file information. Please try sending the photo again."))
            return

        file_io = await bot.download_file(file_info.file_path)
        original_image_bytes = file_io.read()

        unique_id = photo.file_unique_id
        await image_cache.cache_image_bytes(unique_id, original_image_bytes, "image/jpeg", cache_pool)

        data = await state.get_data()
        photos_collected = data.get("photos_collected", [])

        if any(p["file_unique_id"] == unique_id for p in photos_collected):
            await status_msg.edit_text(_("You've already sent this photo. Please send a different one."))
            return

        photos_collected.append({
            "file_id": photo.file_id,
            "file_unique_id": unique_id,
        })
        await state.update_data(photos_collected=photos_collected)

        if len(photos_collected) < 2:
            await status_msg.edit_text(_("Perfect! Now, please send the photo of the second person."))
        else:
            await status_msg.delete()
            # --- REFACTORED: Call the new transition function ---
            await proceed_to_child_params(message, state)

    except Exception as e:
        # Use a proper logger in a real application
        print(f"Error processing photo: {e}")
        await status_msg.edit_text(_("I couldn't process this image. Please try another one or /cancel."))
# aiogram_bot_template/handlers/photo_handler.py
from redis.asyncio import Redis
import mimetypes
import asyncpg
import structlog

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram.utils.i18n import gettext as _

from aiogram_bot_template.data.constants import GenerationType, ImageRole
from aiogram_bot_template.keyboards.inline.child_age import age_selection_kb
from aiogram_bot_template.services import image_cache, face_processor
from aiogram_bot_template.states.user import Generation
from aiogram_bot_template.utils.status_manager import StatusMessageManager
from aiogram_bot_template.db.db_api.storages import PostgresConnection
from aiogram_bot_template.db.repo import generations as generations_repo


router = Router(name="photo-handler")


async def _proceed_after_photos_collected(
    message: Message,
    state: FSMContext,
    db_pool: asyncpg.Pool,
    business_logger: structlog.typing.FilteringBoundLogger,
) -> None:
    """
    This function now ONLY handles the child generation flow.
    It creates the initial GenerationRequest DB entry and proceeds to option selection.
    """
    user_data = await state.get_data()
    db = PostgresConnection(db_pool, logger=business_logger)

    photos_collected = user_data.get("photos_collected", [])
    roles = [ImageRole.PARENT_1, ImageRole.PARENT_2]

    source_images_dto = [
        (p["file_unique_id"], p["file_id"], role)
        for p, role in zip(photos_collected, roles, strict=True)
    ]

    draft = generations_repo.GenerationRequestDraft(
        user_id=message.from_user.id,
        status="photos_collected",
        referral_source=user_data.get("referral_source"),
        source_images=source_images_dto,
        request_parameters={},
    )
    request_id = await generations_repo.create_generation_request(db, draft)
    # Set both the current request_id and the root_request_id for the session
    await state.update_data(request_id=request_id, root_request_id=request_id)
    business_logger.info(
        "GenerationRequest created for child generation", 
        request_id=request_id,
        root_request_id=request_id
    )

    await message.answer(
        _(
            "Excellent, both photos are uploaded.\n\n"
            "Next, please choose the desired age group for the child:"
        ),
        reply_markup=age_selection_kb(),
    )
    await state.set_state(Generation.waiting_for_options)


@router.message(Generation.collecting_inputs, F.photo)
async def process_photo_input(
    message: Message,
    state: FSMContext,
    bot: Bot,
    cache_pool: Redis,
    db_pool: asyncpg.Pool,
    business_logger: structlog.typing.FilteringBoundLogger,
) -> None:
    """
    A unified handler for receiving photos. It now includes face detection
    and cropping for the child generation flow.
    """
    photo = message.photo[-1]

    # 1. Download the original photo bytes
    file_info = await bot.get_file(photo.file_id)
    if not file_info.file_path:
        await message.answer(_("I couldn't process this image. Please try sending it again."))
        return

    file_io = await bot.download_file(file_info.file_path)
    original_bytes = file_io.read()

    data = await state.get_data()
    generation_type = data.get("generation_type")

    final_image_bytes = original_bytes
    content_type = mimetypes.guess_type(file_info.file_path)[0] or "image/jpeg"

    # 2. If it's for child generation, process the face
    if generation_type == GenerationType.CHILD_GENERATION:
        status_msg = await message.answer(_("Checking your photo... 🧐"))
        # We ensure the status message is visible for at least 1.5s
        status_manager = StatusMessageManager(bot, status_msg.chat.id, status_msg.message_id, min_duration=1.5)

        status, processed_bytes = face_processor.detect_and_crop_face(original_bytes)

        if status == "NO_FACE":
            await status_manager.delete()  # Delete the "checking" message
            await message.answer(_("I can't seem to find a clear face in this photo. Could you try another one that's more of a close-up portrait? 👱‍♀️"))
            return

        if status == "MULTIPLE_FACES":
            await status_manager.delete()  # Delete the "checking" message
            await message.answer(_("Oops, I see multiple people here! To work my magic, I need a photo with just one person in it. 👤"))
            return

        # Success! Update status, let it show for a moment, then delete.
        await status_manager.update(_("✅ Face found!"))
        await status_manager.delete()

        final_image_bytes = processed_bytes
        content_type = "image/png"  # Our processor always returns PNG

    # 3. Cache the final image (original or cropped)
    await image_cache.cache_image_bytes(photo.file_unique_id, final_image_bytes, content_type, cache_pool)

    # 4. Proceed with the FSM logic
    photos_needed = data.get("photos_needed", 1)
    photos_collected = data.get("photos_collected", [])

    if any(p["file_unique_id"] == photo.file_unique_id for p in photos_collected):
        await message.answer(
            _("It looks like you sent the same photo twice. Please send a different photo for the second parent.")
        )
        return

    photo_info = {
        "file_id": photo.file_id,
        "file_unique_id": photo.file_unique_id,
    }
    photos_collected.append(photo_info)
    await state.update_data(photos_collected=photos_collected)

    if len(photos_collected) < photos_needed:
        # If the photo is part of a group, don't prompt for the next one yet.
        # Just wait for the next photo in the group to arrive.
        if message.media_group_id:
            return

        await message.answer(
            _("Perfect! I've got the first one. Now, please send me the photo of the second parent. 📸")
        )
    else:
        # The 'generation_type' argument is removed as the function no longer needs it.
        await _proceed_after_photos_collected(
            message, state, db_pool, business_logger
        )

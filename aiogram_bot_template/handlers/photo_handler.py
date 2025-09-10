# aiogram_bot_template/handlers/photo_handler.py
import asyncpg
import structlog
from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram.utils.i18n import gettext as _
from redis.asyncio import Redis

from aiogram_bot_template.data.constants import ImageRole
from aiogram_bot_template.data.settings import settings
from aiogram_bot_template.db.db_api.storages import PostgresConnection
from aiogram_bot_template.db.repo import generations as generations_repo
from aiogram_bot_template.db.repo import users as users_repo
from aiogram_bot_template.keyboards.inline.quality import quality_kb
from aiogram_bot_template.services import image_cache, photo_processing
from aiogram_bot_template.states.user import Generation

router = Router(name="photo-handler")


async def proceed_to_quality_selection(
    message: Message, state: FSMContext, db_pool: asyncpg.Pool,
    business_logger: structlog.typing.FilteringBoundLogger
) -> None:
    user_data = await state.get_data()
    db = PostgresConnection(db_pool, logger=business_logger)
    user_id = message.from_user.id

    photos = user_data.get("photos_collected", [])
    roles = [ImageRole.PHOTO_1, ImageRole.PHOTO_2]

    source_images_dto = [
        (p["original_file_unique_id"], p["original_file_id"], role)
        for p, role in zip(photos, roles)
    ]

    draft = generations_repo.GenerationRequestDraft(
        user_id=user_id, status="photos_collected", source_images=source_images_dto
    )
    request_id = await generations_repo.create_generation_request(db, draft)
    await state.update_data(request_id=request_id)

    is_in_whitelist = user_id in settings.free_trial_whitelist
    has_used_trial = await users_repo.get_user_trial_status(db, user_id)
    is_trial_available = is_in_whitelist or not has_used_trial

    await message.answer(
        _("Excellent, both photos are uploaded. Now, please choose the quality for your portrait."),
        reply_markup=quality_kb(is_trial_available=is_trial_available),
    )
    await state.set_state(Generation.waiting_for_quality)


@router.message(Generation.collecting_photos, F.photo)
async def process_photo_input(
    message: Message, state: FSMContext, bot: Bot, cache_pool: Redis,
    db_pool: asyncpg.Pool, business_logger: structlog.typing.FilteringBoundLogger
) -> None:
    photo = message.photo[-1]
    status_msg = await message.answer(_("Processing your photo... ⏳"))

    try:
        file_info = await bot.get_file(photo.file_id)
        if not file_info.file_path:
            await status_msg.edit_text(_("I couldn't get file information. Please try sending the photo again."))
            return

        file_io = await bot.download_file(file_info.file_path)
        original_image_bytes = file_io.read()

        # <<< ИЗМЕНЕНИЕ: Получаем объект с тремя кропами
        processed_result = photo_processing.preprocess_image(original_image_bytes)
        if not processed_result:
            await status_msg.edit_text(_("I couldn't detect a clear face. Please send another one."))
            return

        # <<< ИЗМЕНЕНИЕ: Кэшируем все три версии
        base_unique_id = photo.file_unique_id
        
        # Кэшируем оригинал
        await image_cache.cache_image_bytes(base_unique_id, original_image_bytes, "image/jpeg", cache_pool)
        
        # Кэшируем обработанные версии
        processed_uids = {}
        for crop_name in ["headshot", "portrait", "half_body"]:
            uid = f"{base_unique_id}_{crop_name}"
            image_bytes = getattr(processed_result, crop_name)
            await image_cache.cache_image_bytes(uid, image_bytes, "image/jpeg", cache_pool)
            processed_uids[crop_name] = uid
        
        business_logger.info("Cached original and all processed image versions", original_id=base_unique_id)

        # <<< ИЗМЕНЕНИЕ: Обновляем FSM новой структурой данных
        data = await state.get_data()
        photos_collected = data.get("photos_collected", [])

        if any(p["original_file_unique_id"] == base_unique_id for p in photos_collected):
            await status_msg.edit_text(_("You've already sent this photo. Please send a different one."))
            return

        photos_collected.append({
            "original_file_id": photo.file_id,
            "original_file_unique_id": base_unique_id,
            "processed_files": processed_uids, # Сохраняем словарь с ID
        })
        await state.update_data(photos_collected=photos_collected)

        if len(photos_collected) < 2:
            await status_msg.edit_text(_("Perfect! Now, please send the photo of the second person."))
        else:
            await status_msg.delete()
            await proceed_to_quality_selection(message, state, db_pool, business_logger)

    except Exception:
        business_logger.exception("Failed to process photo")
        await status_msg.edit_text(_("I couldn't process this image. Please try another one or /cancel."))
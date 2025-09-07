# aiogram_bot_template/handlers/photo_handler.py
from redis.asyncio import Redis
import mimetypes
import asyncpg
import structlog

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram.utils.i18n import gettext as _

from aiogram_bot_template.data.constants import ImageRole
# --- ИЗМЕНЕНИЕ: Импортируем settings для доступа к whitelist ---
from aiogram_bot_template.data.settings import settings
from aiogram_bot_template.services import image_cache
from aiogram_bot_template.states.user import Generation
from aiogram_bot_template.db.db_api.storages import PostgresConnection
from aiogram_bot_template.db.repo import generations as generations_repo, users as users_repo
from aiogram_bot_template.keyboards.inline.quality import quality_kb

router = Router(name="photo-handler")

async def proceed_to_quality_selection(
    message: Message,
    state: FSMContext,
    db_pool: asyncpg.Pool,
    business_logger: structlog.typing.FilteringBoundLogger,
) -> None:
    user_data = await state.get_data()
    db = PostgresConnection(db_pool, logger=business_logger)
    user_id = message.from_user.id # Получаем ID пользователя

    photos = user_data.get("photos_collected", [])
    roles = [ImageRole.PHOTO_1, ImageRole.PHOTO_2]
    
    source_images_dto = [
        (p["file_unique_id"], p["file_id"], role)
        for p, role in zip(photos, roles)
    ]

    draft = generations_repo.GenerationRequestDraft(
        user_id=user_id,
        status="photos_collected",
        source_images=source_images_dto,
    )
    request_id = await generations_repo.create_generation_request(db, draft)
    await state.update_data(request_id=request_id)

    # --- ИЗМЕНЕНИЕ: Правильная логика проверки доступности бесплатной попытки ---
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
    message: Message,
    state: FSMContext,
    bot: Bot,
    cache_pool: Redis,
    db_pool: asyncpg.Pool,
    business_logger: structlog.typing.FilteringBoundLogger,
) -> None:
    # Этот хэндлер остается без изменений
    photo = message.photo[-1]
    
    file_info = await bot.get_file(photo.file_id)
    if not file_info.file_path:
        await message.answer(_("I couldn't process this image. Please try again."))
        return

    file_io = await bot.download_file(file_info.file_path)
    image_bytes = file_io.read()
    content_type = mimetypes.guess_type(file_info.file_path)[0] or "image/jpeg"

    await image_cache.cache_image_bytes(photo.file_unique_id, image_bytes, content_type, cache_pool)

    data = await state.get_data()
    photos_collected = data.get("photos_collected", [])

    if any(p["file_unique_id"] == photo.file_unique_id for p in photos_collected):
        await message.answer(_("You've already sent this photo. Please send a different one."))
        return

    photos_collected.append({"file_id": photo.file_id, "file_unique_id": photo.file_unique_id})
    await state.update_data(photos_collected=photos_collected)

    if len(photos_collected) < 2:
        await message.answer(_("Perfect! Now, please send the photo of the second person."))
    else:
        await proceed_to_quality_selection(message, state, db_pool, business_logger)
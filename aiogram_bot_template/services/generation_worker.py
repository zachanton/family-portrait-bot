# aiogram_bot_template/services/generation_worker.py
import asyncio
from contextlib import suppress

import asyncpg
import structlog
import uuid
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile
from aiogram.utils.i18n import gettext as _
from redis.asyncio import Redis

from aiogram_bot_template.data.constants import GenerationType
from aiogram_bot_template.data.settings import settings
from aiogram_bot_template.db.db_api.storages import PostgresConnection
from aiogram_bot_template.db.repo import generations as generations_repo
from aiogram_bot_template.dto.post_generation_context import PostGenerationContext
from aiogram_bot_template.keyboards.inline import feedback, next_step
from aiogram_bot_template.services import image_cache, image_generation_service as ai_service
from aiogram_bot_template.services.google_sheets_logger import GoogleSheetsLogger
from aiogram_bot_template.services.pipelines.group_photo import GroupPhotoPipeline
from aiogram_bot_template.states.user import Generation
from aiogram_bot_template.utils.status_manager import StatusMessageManager

# Helper function for debugging
async def _send_debug_image(bot: Bot, chat_id: int, redis: Redis, image_uid: str, caption: str):
    """Fetches an image from cache and sends it to the user for debugging."""
    try:
        image_bytes, _ = await image_cache.get_cached_image_bytes(image_uid, redis)
        if image_bytes:
            photo = BufferedInputFile(image_bytes, f"{image_uid}.jpg")
            await bot.send_photo(chat_id=chat_id, photo=photo, caption=caption)
    except Exception:
        pass

async def run_generation_worker(
    bot: Bot,
    chat_id: int,
    status_message_id: int,
    db_pool: asyncpg.Pool,
    business_logger: structlog.typing.FilteringBoundLogger,
    cache_pool: Redis,
    state: FSMContext,
) -> None:
    user_data = await state.get_data()
    request_id = user_data.get("request_id")

    log = business_logger.bind(req_id=request_id, chat_id=chat_id)
    db = PostgresConnection(db_pool, logger=log, decode_json=True)
    status = StatusMessageManager(bot, chat_id, status_message_id)

    try:
        if not request_id:
            raise ValueError("request_id not found in FSM state for worker.")

        db_data = await generations_repo.get_request_details_with_sources(db, request_id)
        if not db_data:
            raise ValueError(f"GenerationRequest with id={request_id} not found in DB.")

        gen_data = {**user_data, **db_data}
        gen_data["type"] = GenerationType.GROUP_PHOTO.value
        gen_data["quality_level"] = gen_data["quality"]
        
        # --- ВОССТАНОВЛЕННОЕ И УЛУЧШЕННОЕ ЛОГИРОВАНИЕ ---
        photos_collected = gen_data.get("photos_collected", [])
        if len(photos_collected) == 2:
            photo1_uid = photos_collected[0].get("processed_files", {}).get("half_body")
            photo2_uid = photos_collected[1].get("processed_files", {}).get("half_body")
            if photo1_uid and photo2_uid:
                await _send_debug_image(bot, chat_id, cache_pool, photo1_uid, "DEBUG: 1. Индивидуально обработанное фото 1")
                await _send_debug_image(bot, chat_id, cache_pool, photo2_uid, "DEBUG: 2. Индивидуально обработанное фото 2")
        # --- КОНЕЦ ЛОГИРОВАНИЯ ---
        
        await generations_repo.update_generation_request_status(db, request_id, "processing")

        pipeline = GroupPhotoPipeline(bot, gen_data, log, status.update, cache_pool)
        pipeline_output = await pipeline.prepare_data()

        # --- ВОССТАНОВЛЕННОЕ И УЛУЧШЕННОЕ ЛОГИРОВАНИЕ ---
        if harmonized_uids := pipeline_output.metadata.get("harmonized_uids"):
            await _send_debug_image(bot, chat_id, cache_pool, harmonized_uids[0], "DEBUG: 3. Гармонизированное фото 1")
            await _send_debug_image(bot, chat_id, cache_pool, harmonized_uids[1], "DEBUG: 4. Гармонизированное фото 2")
            
        if composite_uid := pipeline_output.metadata.get("composite_uid"):
            await _send_debug_image(bot, chat_id, cache_pool, composite_uid, "DEBUG: 5. Склеенное изображение (вход для AI)")
        # --- КОНЕЦ ЛОГИРОВАНИЯ ---

        result, error_meta = await pipeline.run_generation(pipeline_output)

        if not result:
            raise RuntimeError(f"AI service failed: {error_meta}")

        await status.delete()

        photo = BufferedInputFile(result.image_bytes, "group_photo.png")
        sent_message = await bot.send_photo(chat_id=chat_id, photo=photo, caption=pipeline_output.caption)
        
        result_image_unique_id = sent_message.photo[-1].file_unique_id
        result_file_id = sent_message.photo[-1].file_id
        
        asyncio.create_task(
            GoogleSheetsLogger().log_generation(
                gen_data=gen_data,
                result=result,
                output_image_unique_id=result_image_unique_id,
            )
        )

        continue_key = uuid.uuid4().hex[:16]
        
        control_message_text = _("What would you like to do next?")
        reply_markup = next_step.get_next_step_keyboard(continue_key, request_id)

        if settings.collect_feedback:
            control_message_text = _("Did you like the result?")
            reply_markup = feedback.feedback_kb(0, request_id, continue_key)

        new_control_message = await bot.send_message(chat_id, control_message_text, reply_markup=reply_markup)
        
        log_entry = generations_repo.GenerationLog(
            request_id=request_id,
            type=GenerationType.GROUP_PHOTO.value,
            status="completed",
            quality_level=gen_data.get("quality"),
            trial_type=gen_data.get("trial_type"),
            seed=result.request_payload.get("seed"),
            generation_time_ms=result.generation_time_ms,
            api_request_payload=result.request_payload,
            api_response_payload=result.response_payload,
            result_image_unique_id=result_image_unique_id,
            result_message_id=sent_message.message_id,
            result_file_id=result_file_id,
            caption=pipeline_output.caption,
            control_message_id=new_control_message.message_id,
        )
        generation_id = await generations_repo.create_generation_log(db, log_entry)
        log = log.bind(gen_id=generation_id)
        
        if settings.collect_feedback:
            final_feedback_kb = feedback.feedback_kb(generation_id, request_id, continue_key)
            with suppress(TelegramBadRequest):
                await bot.edit_message_reply_markup(
                    chat_id=chat_id, message_id=new_control_message.message_id, reply_markup=final_feedback_kb
                )

        await generations_repo.update_generation_request_status(db, request_id, "completed")
        await image_cache.cache_image_bytes(result_image_unique_id, result.image_bytes, result.content_type, cache_pool)

        context_to_store = PostGenerationContext(
            request_id=request_id,
            generation_id=generation_id,
            generation_type=GenerationType.GROUP_PHOTO,
            file_id=result_file_id,
            unique_id=result_image_unique_id,
        )
        await cache_pool.set(f"continue_edit:{continue_key}", context_to_store.model_dump_json(), ex=86400)
        
        await state.clear()
        current_state = Generation.waiting_for_next_action if not settings.collect_feedback else Generation.waiting_for_feedback
        await state.set_state(current_state)
        await state.update_data(
            feedback_continue_key=continue_key,
            feedback_generation_id=generation_id,
            feedback_request_id=request_id
        )

    except Exception:
        log.exception("An unhandled error occurred in the generation worker.")
        if status_message_id:
             await status.delete()
        await bot.send_message(chat_id, _("😔 An unexpected error occurred. Please try again with /start."))
        if request_id:
            await generations_repo.update_generation_request_status(db, request_id, "failed_internal")
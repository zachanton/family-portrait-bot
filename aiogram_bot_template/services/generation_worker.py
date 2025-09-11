# aiogram_bot_template/services/generation_worker.py
import asyncio
import random
import uuid
from asyncio import Event
from contextlib import suppress

import asyncpg
import structlog
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
from aiogram_bot_template.services import (
    image_cache,
    image_generation_service as ai_service,
    similarity_scorer,
)
from aiogram_bot_template.services.google_sheets_logger import GoogleSheetsLogger
from aiogram_bot_template.services.pipelines.group_photo import GroupPhotoPipeline
from aiogram_bot_template.states.user import Generation
from aiogram_bot_template.utils.status_manager import StatusMessageManager


# Helper function for debugging
async def _send_debug_image(
    bot: Bot, chat_id: int, redis: Redis, image_uid: str, caption: str
):
    """Fetches an image from cache and sends it to the user for debugging."""
    try:
        image_bytes, _ = await image_cache.get_cached_image_bytes(image_uid, redis)
        if image_bytes:
            photo = BufferedInputFile(image_bytes, f"{image_uid}.jpg")
            await bot.send_photo(chat_id=chat_id, photo=photo, caption=caption)
    except Exception:
        pass


async def _update_status_periodically(
    bot: Bot, chat_id: int, message_id: int, stop_event: asyncio.Event
) -> None:
    messages = [
        _("🎨 Applying final touches..."),
        _("✨ Polishing the details..."),
        _("🔮 Consulting the AI spirits..."),
        _("⏳ Almost there..."),
    ]
    last_message = ""
    while not stop_event.is_set():
        try:
            # Wait for the event to be set, with a timeout
            await asyncio.wait_for(stop_event.wait(), timeout=15)
        except asyncio.TimeoutError:
            # If the timeout occurs, the event was not set, so update the status
            new_message = random.choice(
                [m for m in messages if m != last_message] or messages
            )
            last_message = new_message
            with suppress(TelegramBadRequest):
                await bot.edit_message_text(
                    text=new_message, chat_id=chat_id, message_id=message_id
                )


async def _calculate_and_update_similarity_caption(
    bot: Bot,
    chat_id: int,
    message_id: int,
    original_caption: str,
    cache_pool: Redis,
    log: structlog.typing.FilteringBoundLogger,
    gen_data: dict,
    result_image_bytes: bytes,
):
    """
    Calculates similarity scores and updates the message caption.
    Runs in the background to not block the main flow.
    """
    try:
        log.info("Starting background similarity scoring.")
        photos_collected = gen_data.get("photos_collected", [])
        photo1_uid = photos_collected[0].get("processed_files", {}).get("half_body")
        photo2_uid = photos_collected[1].get("processed_files", {}).get("half_body")

        if not photo1_uid or not photo2_uid:
            log.warning("Could not find processed UIDs for similarity scoring.")
            return

        photo1_bytes, _ = await image_cache.get_cached_image_bytes(
            photo1_uid, cache_pool
        )
        photo2_bytes, _ = await image_cache.get_cached_image_bytes(
            photo2_uid, cache_pool
        )

        if not photo1_bytes or not photo2_bytes:
            log.warning(
                "Could not retrieve original photos from cache for similarity scoring."
            )
            return

        left_gen_bytes, right_gen_bytes = similarity_scorer.crop_generated_image(
            result_image_bytes
        )

        if not left_gen_bytes or not right_gen_bytes:
            log.warning("Failed to crop generated image for similarity scoring.")
            return

        # Correctly call the insightface-based scorer
        score1_task = similarity_scorer.get_face_similarity_score(
            single_image_bytes=photo1_bytes, pair_image_bytes=left_gen_bytes
        )
        score2_task = similarity_scorer.get_face_similarity_score(
            single_image_bytes=photo2_bytes, pair_image_bytes=right_gen_bytes
        )

        score1, score2 = await asyncio.gather(score1_task, score2_task)

        # Convert cosine similarity [-1, 1] to a more intuitive percentage [0, 100]
        # by scaling and clamping the range [0, 1]
        score1_percent = ((score1 + 1) / 2) if score1 is not None else None
        score2_percent = ((score2 + 1) / 2) if score2 is not None else None

        score1_str = f"{score1_percent:.1%}" if score1_percent is not None else "N/A"
        score2_str = f"{score2_percent:.1%}" if score2_percent is not None else "N/A"

        debug_caption = (
            f"\n\n---\n"
            f"<b>Debug Info:</b>\n"
            f"Similarity (Person 1): {score1_str}\n"
            f"Similarity (Person 2): {score2_str}"
        )

        new_caption = original_caption + debug_caption

        with suppress(TelegramBadRequest):
            await bot.edit_message_caption(
                chat_id=chat_id, message_id=message_id, caption=new_caption
            )
        log.info(
            "Successfully updated caption with similarity scores.",
            score1=score1_str,
            score2=score2_str,
        )

    except Exception:
        log.exception("An error occurred in the background similarity scoring task.")


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

        db_data = await generations_repo.get_request_details_with_sources(
            db, request_id
        )
        if not db_data:
            raise ValueError(
                f"GenerationRequest with id={request_id} not found in DB."
            )

        gen_data = {**user_data, **db_data}
        gen_data["type"] = GenerationType.GROUP_PHOTO.value
        gen_data["quality_level"] = gen_data["quality"]

        # --- RESTORED DEBUG IMAGES (PART 1) ---
        photos_collected = gen_data.get("photos_collected", [])
        if len(photos_collected) == 2:
            photo1_uid = photos_collected[0].get("processed_files", {}).get("half_body")
            photo2_uid = photos_collected[1].get("processed_files", {}).get("half_body")
            if photo1_uid and photo2_uid:
                await _send_debug_image(
                    bot,
                    chat_id,
                    cache_pool,
                    photo1_uid,
                    "DEBUG: 1. Individually processed photo 1 (half_body)",
                )
                await _send_debug_image(
                    bot,
                    chat_id,
                    cache_pool,
                    photo2_uid,
                    "DEBUG: 2. Individually processed photo 2 (half_body)",
                )
        # --- END OF RESTORED DEBUG ---

        await generations_repo.update_generation_request_status(
            db, request_id, "processing"
        )

        pipeline = GroupPhotoPipeline(bot, gen_data, log, status.update, cache_pool)
        pipeline_output = await pipeline.prepare_data()

        # --- RESTORED DEBUG IMAGES (PART 2) ---
        if composite_uid := pipeline_output.metadata.get("composite_uid"):
            await _send_debug_image(
                bot,
                chat_id,
                cache_pool,
                composite_uid,
                "DEBUG: 3. Composite image (input for AI)",
            )
        # --- END OF RESTORED DEBUG ---
        
        # --- INTEGRATION OF PERIODIC STATUS UPDATER ---
        stop_event = Event()
        status_updater_task = asyncio.create_task(
            _update_status_periodically(
                bot, chat_id, status_message_id, stop_event
            )
        )
        
        result, error_meta = None, None
        try:
            result, error_meta = await pipeline.run_generation(pipeline_output)
        finally:
            # Ensure the background task is always stopped
            stop_event.set()
            status_updater_task.cancel()
        # --- END OF INTEGRATION ---

        if not result:
            raise RuntimeError(f"AI service failed: {error_meta}")

        await status.delete()

        photo = BufferedInputFile(result.image_bytes, "group_photo.png")
        sent_message = await bot.send_photo(
            chat_id=chat_id, photo=photo, caption=pipeline_output.caption
        )

        # Spawn a background task to calculate and add similarity scores
        asyncio.create_task(
            _calculate_and_update_similarity_caption(
                bot=bot,
                chat_id=chat_id,
                message_id=sent_message.message_id,
                original_caption=pipeline_output.caption,
                cache_pool=cache_pool,
                log=log,
                gen_data=gen_data,
                result_image_bytes=result.image_bytes,
            )
        )

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

        new_control_message = await bot.send_message(
            chat_id, control_message_text, reply_markup=reply_markup
        )

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
            final_feedback_kb = feedback.feedback_kb(
                generation_id, request_id, continue_key
            )
            with suppress(TelegramBadRequest):
                await bot.edit_message_reply_markup(
                    chat_id=chat_id,
                    message_id=new_control_message.message_id,
                    reply_markup=final_feedback_kb,
                )

        await generations_repo.update_generation_request_status(
            db, request_id, "completed"
        )
        await image_cache.cache_image_bytes(
            result_image_unique_id, result.image_bytes, result.content_type, cache_pool
        )

        context_to_store = PostGenerationContext(
            request_id=request_id,
            generation_id=generation_id,
            generation_type=GenerationType.GROUP_PHOTO,
            file_id=result_file_id,
            unique_id=result_image_unique_id,
        )
        await cache_pool.set(
            f"continue_edit:{continue_key}",
            context_to_store.model_dump_json(),
            ex=86400,
        )

        await state.clear()
        current_state = (
            Generation.waiting_for_next_action
            if not settings.collect_feedback
            else Generation.waiting_for_feedback
        )
        await state.set_state(current_state)
        await state.update_data(
            feedback_continue_key=continue_key,
            feedback_generation_id=generation_id,
            feedback_request_id=request_id,
        )

    except Exception:
        log.exception("An unhandled error occurred in the generation worker.")
        if status_message_id:
            await status.delete()
        await bot.send_message(
            chat_id, _("😔 An unexpected error occurred. Please try again with /start.")
        )
        if request_id:
            await generations_repo.update_generation_request_status(
                db, request_id, "failed_internal"
            )
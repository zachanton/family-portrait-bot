# aiogram_bot_template/services/generation_worker.py
import asyncio
import random
import uuid
import re
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
from aiogram_bot_template.keyboards.inline import next_step
from aiogram_bot_template.services import (
    image_cache,
    prompt_enhancer,
    similarity_scorer,
)
from aiogram_bot_template.services.google_sheets_logger import GoogleSheetsLogger
from aiogram_bot_template.services.pipelines.group_photo import GroupPhotoPipeline
from aiogram_bot_template.states.user import Generation
from aiogram_bot_template.utils.status_manager import StatusMessageManager
from aiogram_bot_template.services.prompting.factory import get_prompt_strategy
from aiogram_bot_template.services.prompting.fal_strategy import STYLE_PROMPTS, get_translated_style_name


async def _send_debug_image(
    bot: Bot, chat_id: int, redis: Redis, image_uid: str, caption: str
):
    """Fetches an image from cache and sends it to the user for debugging."""
    try:
        image_bytes, _ = await image_cache.get_cached_image_bytes(image_uid, redis)
        if image_bytes:
            photo = BufferedInputFile(image_bytes, f"{image_uid}.jpg")
            await bot.send_photo(chat_id=chat_id, photo=photo, caption=caption)
    except Exception as e:
        structlog.get_logger(__name__).warning("Failed to send debug image", error=str(e))

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
    Calculates similarity scores and updates the message caption in the background.
    """
    try:
        log.info("Starting background similarity scoring.")
        photos_collected = gen_data.get("photos_collected", [])
        photo1_uid = photos_collected[0].get("file_unique_id")
        photo2_uid = photos_collected[1].get("file_unique_id")

        if not photo1_uid or not photo2_uid:
            log.warning("Could not find original UIDs for similarity scoring.")
            return

        photo1_bytes, _ = await image_cache.get_cached_image_bytes(photo1_uid, cache_pool)
        photo2_bytes, _ = await image_cache.get_cached_image_bytes(photo2_uid, cache_pool)

        if not photo1_bytes or not photo2_bytes:
            log.warning("Could not retrieve original photos from cache for similarity scoring.")
            return

        left_gen_bytes, right_gen_bytes = similarity_scorer.crop_generated_image(
            result_image_bytes
        )

        if not left_gen_bytes or not right_gen_bytes:
            log.warning("Failed to crop generated image for similarity scoring.")
            return

        score1_task = similarity_scorer.get_face_similarity_score(
            single_image_bytes=photo1_bytes, pair_image_bytes=left_gen_bytes
        )
        score2_task = similarity_scorer.get_face_similarity_score(
            single_image_bytes=photo2_bytes, pair_image_bytes=right_gen_bytes
        )
        score1, score2 = await asyncio.gather(score1_task, score2_task)
        
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
    quality_level = user_data.get("quality")
    trial_type = user_data.get("trial_type")

    log = business_logger.bind(req_id=request_id, chat_id=chat_id)
    db = PostgresConnection(db_pool, logger=log, decode_json=True)
    status = StatusMessageManager(bot, chat_id, status_message_id)

    try:
        if not request_id or quality_level is None:
            raise ValueError("request_id or quality level not found in FSM state for worker.")

        tier_config = settings.group_photo.tiers.get(quality_level)
        if not tier_config:
            raise ValueError(f"Tier configuration for quality level {quality_level} not found.")

        generation_count = tier_config.count
        if generation_count <= 0:
            raise ValueError("Tier count must be a positive number.")
            
        chosen_style = random.choice(list(STYLE_PROMPTS.keys()))
        chosen_style = 'golden_hour'
        log.info("Photoshoot plan created", style=chosen_style, count=generation_count)

        db_data = await generations_repo.get_request_details_with_sources(db, request_id)
        if not db_data:
            raise ValueError(f"GenerationRequest with id={request_id} not found in DB.")

        gen_data = {**user_data, **db_data, "type": GenerationType.GROUP_PHOTO.value, "quality_level": quality_level}
        await generations_repo.update_generation_request_status(db, request_id, "processing")

        pipeline = GroupPhotoPipeline(bot, gen_data, log, status.update, cache_pool)
        pipeline_output = await pipeline.prepare_data()
        
        composite_image_url = pipeline_output.request_payload.get("image_urls", [None])[0]
        if not composite_image_url:
            raise ValueError("Composite image URL could not be determined.")
        
        if composite_uid := pipeline_output.metadata.get("composite_uid"):
            await _send_debug_image(bot=bot, chat_id=chat_id, redis=cache_pool, image_uid=composite_uid, caption="DEBUG: Composite image (Identity Source)")

        await status.update(_("✍️ Analyzing facial features for the photoshoot..."))
        initial_identity_data = await prompt_enhancer.get_enhanced_prompt_data(image_url=composite_image_url)
        identity_lock_text = prompt_enhancer.format_enhanced_data_as_text(initial_identity_data) if initial_identity_data else "IDENTITY LOCK: Faces must match the reference image."
        log.info("Persistent identity lock created for the photoshoot.", text_length=len(identity_lock_text))
        
        last_sent_message = None
        previous_shot_url = None
        source_generation_id = None
        first_successful_shot_url = None
        
        # --- KEY CHANGE: List to store used shot types for the session ---
        used_shot_types: list[str] = []
        
        strategy = get_prompt_strategy(tier_config.client)
        
        for i in range(generation_count):
            current_iteration = i + 1
            log_task = log.bind(style=chosen_style, sequence=f"{current_iteration}/{generation_count}")
            log_task.info("Starting generation of a photoshoot frame.")
            
            current_payload = pipeline_output.request_payload.copy()
            
            pose_composition_text: str
            if i == 0:
                await status.update(_("🎨 Generating shot {current} of {total}...").format(current=current_iteration, total=generation_count))
                pose_composition_text = "Subjects are posed naturally, cheek-to-temple and shoulder-to-shoulder, with a slight inward head tilt, both looking at the camera. ~12% overlap for natural occlusion; align eye lines."
                # The first shot is implicitly a 'Close-Up'
                used_shot_types.append('Close-Up')
            
                style_payload = strategy.create_group_photo_payload(style=chosen_style)
                prompt_template = style_payload.get("prompt", "")
                current_payload["image_urls"] = [composite_image_url]
            else:
                if not previous_shot_url or not first_successful_shot_url:
                    log_task.error("Cannot proceed with photoshoot, a required previous frame failed.")
                    break

                await status.update(_("🎬 Directing the next shot ({current}/{total})...").format(current=current_iteration, total=generation_count))
                
                translated_style_name = get_translated_style_name(chosen_style)
                
                # --- KEY CHANGE: Pass the list of used shot types to the enhancer ---
                next_frame_data = await prompt_enhancer.get_next_frame_data(
                    previous_shot_url, 
                    translated_style_name,
                    used_shot_types=used_shot_types
                )

                if not next_frame_data:
                    log_task.warning("Could not get next frame data from enhancer. Re-using default pose as fallback.")
                    pose_composition_text = "Subjects are posed naturally, cheek-to-temple and shoulder-to-shoulder, with a slight inward head tilt, both looking at the camera. ~12% overlap for natural occlusion; align eye lines."
                else:
                    pose_composition_text = prompt_enhancer.format_next_frame_data_as_text(next_frame_data)
                    # --- KEY CHANGE: Add the new shot type to our memory ---
                    used_shot_types.append(next_frame_data.camera.shot_type)

                style_payload = strategy.create_group_photo_next_payload(style=chosen_style)
                prompt_template = style_payload.get("prompt", "")
                
                current_payload["image_urls"] = [first_successful_shot_url, composite_image_url]
                
            temp_prompt = prompt_template.replace("{{IDENTITY_LOCK_DATA}}", identity_lock_text)
            final_prompt = temp_prompt.replace("{{POSE_AND_COMPOSITION_DATA}}", pose_composition_text)
            
            current_payload.update(style_payload)
            current_payload["prompt"] = final_prompt
            current_payload["seed"] = random.randint(1, 1_000_000)
            
            log_task.info("Final prompt prepared for generation", final_prompt_summary=final_prompt)

            result, error_meta = await pipeline.run_generation(
                pipeline_output, payload_override=current_payload
            )

            if not result:
                log_task.error("AI service failed for this frame", meta=error_meta)
                # If a frame fails, we shouldn't add its intended shot_type to the used list
                # as it was never shown to the user.
                if i > 0:
                    used_shot_types.pop() # Remove the last added shot_type
                    await bot.send_message(chat_id, _("Sorry, there was a problem creating the next shot. The photoshoot will end here."))
                break

            translated_style_name = get_translated_style_name(chosen_style)
            caption_text = _("Style: {style_name} (Shot {current}/{total})").format(
                style_name=translated_style_name, current=current_iteration, total=generation_count
            )

            photo = BufferedInputFile(result.image_bytes, f"photoshoot_{current_iteration}.png")
            last_sent_message = await bot.send_photo(chat_id=chat_id, photo=photo, caption=caption_text)

            result_image_unique_id = last_sent_message.photo[-1].file_unique_id
            result_file_id = last_sent_message.photo[-1].file_id

            await image_cache.cache_image_bytes(result_image_unique_id, result.image_bytes, result.content_type, cache_pool)
            
            previous_shot_url = image_cache.get_cached_image_proxy_url(result_image_unique_id)
            
            if i == 0:
                first_successful_shot_url = previous_shot_url
            
            log_entry = generations_repo.GenerationLog(
                request_id=request_id, type=GenerationType.GROUP_PHOTO.value, status="completed",
                quality_level=quality_level, trial_type=trial_type, seed=current_payload["seed"], style=chosen_style,
                generation_time_ms=result.generation_time_ms, 
                api_request_payload=result.request_payload,
                api_response_payload=result.response_payload, 
                enhanced_prompt=final_prompt,
                result_image_unique_id=result_image_unique_id,
                result_message_id=last_sent_message.message_id, result_file_id=result_file_id,
                caption=caption_text,
                sequence_index=i,
                source_generation_id=source_generation_id
            )
            source_generation_id = await generations_repo.create_generation_log(db, log_entry)

        await status.delete()

        if not last_sent_message:
             await bot.send_message(chat_id, _("Unfortunately, there was an issue with the generation and your photoshoot could not be completed. Please try again with /start."))
             await generations_repo.update_generation_request_status(db, request_id, "failed_all_frames")
        else:
            await bot.send_message(chat_id, _("Your photoshoot is complete! What would you like to do next?"), 
                reply_markup=next_step.get_next_step_keyboard("continue", request_id)
            )
            await generations_repo.update_generation_request_status(db, request_id, "completed")

        await state.clear()
        await state.set_state(Generation.waiting_for_next_action)

    except Exception:
        log.exception("An unhandled error occurred in the generation worker.")
        if status_message_id:
            with suppress(TelegramBadRequest):
                await status.delete()
        await bot.send_message(
            chat_id, _("😔 An unexpected error occurred. Please try again with /start.")
        )
        if request_id:
            await generations_repo.update_generation_request_status(
                db, request_id, "failed_internal"
            )
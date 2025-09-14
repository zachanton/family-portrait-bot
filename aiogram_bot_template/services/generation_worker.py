# aiogram_bot_template/services/generation_worker.py
import asyncio
import random
import re
import uuid
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
from aiogram_bot_template.services.prompt_enhancer import EnhancedPromptData
from aiogram_bot_template.services.google_sheets_logger import GoogleSheetsLogger
from aiogram_bot_template.services.pipelines.group_photo import GroupPhotoPipeline
from aiogram_bot_template.states.user import Generation
from aiogram_bot_template.utils.status_manager import StatusMessageManager
from aiogram_bot_template.services.prompting.factory import get_prompt_strategy
from aiogram_bot_template.services.prompting.fal_strategy import STYLE_PROMPTS, get_translated_style_name


def _format_enhanced_parts(data: EnhancedPromptData) -> str:
    """Formats the structured data from the Pydantic model into a readable text block."""
    
    def format_identity_lock(person_data, title):
        lines = [
            title,
            f"* Overall Impression & Essence: {person_data.overall_impression}",
            f"* Face geometry: {person_data.face_geometry}",
            "* Eyes:",
            f"  * Color: {person_data.eyes.color}",
            f"  * Shape: {person_data.eyes.shape}",
            f"* Eyebrows: {person_data.eyebrows}",
            "* Nose (Forensic Breakdown):",
            f"  * Bridge (Dorsum): {person_data.nose.bridge}",
            f"  * Tip (Apex): {person_data.nose.tip}",
            f"  * Nostrils: {person_data.nose.nostrils}",
            f"* Lips: {person_data.lips}",
            f"* Skin: {person_data.skin}",
            f"* Hair: {person_data.hair}",
            f"* Unique details: {person_data.unique_details}",
        ]
        return "\n".join(lines)

    person_a_text = format_identity_lock(
        data.person_a, "IDENTITY LOCK — PERSON A (woman, on the left in the source)"
    )
    person_b_text = format_identity_lock(
        data.person_b, "IDENTITY LOCK — PERSON B (man, on the right in the source)"
    )
    
    cleanup_text = "\n".join([
        "SOURCE-SPECIFIC CLEANUP",
        f"* {data.cleanup.artifacts}",
        f"* {data.cleanup.seam}",
        f"* {data.cleanup.logos}",
    ])

    return f"{person_a_text}\n\n{person_b_text}\n\n{cleanup_text}"


def _construct_final_prompt(base_prompt: str, enhanced_data: EnhancedPromptData) -> str:
    """
    Surgically replaces the generic IDENTITY LOCK section in the base prompt
    with detailed, formatted text from the structured data.
    """
    pattern = re.compile(r"IDENTITY LOCK \(must match the source\).*?STYLE TARGET", re.DOTALL | re.IGNORECASE)
    
    formatted_parts = _format_enhanced_parts(enhanced_data)
    
    replacement_text = f"{formatted_parts}\n\nSTYLE TARGET"

    final_prompt, num_replacements = pattern.subn(replacement_text, base_prompt, count=1)

    if num_replacements == 0:
        return base_prompt

    return final_prompt


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

        # Run scoring in parallel
        score1_task = similarity_scorer.get_face_similarity_score(
            single_image_bytes=photo1_bytes, pair_image_bytes=left_gen_bytes
        )
        score2_task = similarity_scorer.get_face_similarity_score(
            single_image_bytes=photo2_bytes, pair_image_bytes=right_gen_bytes
        )
        score1, score2 = await asyncio.gather(score1_task, score2_task)
        
        # Convert cosine similarity [-1, 1] to percentage [0, 100]
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
    # Most of this function remains the same, only the enhancement part changes
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

        generation_tasks = []
        available_styles = list(STYLE_PROMPTS.keys())
        
        if quality_level == 0:
            style = "golden_hour" if trial_type == "free_trial" else random.choice(available_styles)
            generation_tasks.append({"style": style, "seed": 42})
        else:
            styles_to_use = random.sample(available_styles * tier_config.count, tier_config.count)
            for style in styles_to_use:
                generation_tasks.append({"style": style, "seed": random.randint(0, 2**32 - 1)})
        
        generation_count = len(generation_tasks)
        log.info("Generation plan created", count=generation_count, tasks=generation_tasks)

        db_data = await generations_repo.get_request_details_with_sources(db, request_id)
        if not db_data:
            raise ValueError(f"GenerationRequest with id={request_id} not found in DB.")

        gen_data = {**user_data, **db_data, "type": GenerationType.GROUP_PHOTO.value, "quality_level": quality_level}
        await generations_repo.update_generation_request_status(db, request_id, "processing")

        pipeline = GroupPhotoPipeline(bot, gen_data, log, status.update, cache_pool)
        pipeline_output = await pipeline.prepare_data()

        composite_image_url = None
        if pipeline_output.request_payload.get("image_urls"):
            composite_image_url = pipeline_output.request_payload["image_urls"][0]
        
        if composite_uid := pipeline_output.metadata.get("composite_uid"):
            await _send_debug_image(
                bot=bot, chat_id=chat_id, redis=cache_pool,
                image_uid=composite_uid, caption="DEBUG: Composite image (input for AI)",
            )
        
        last_sent_message = None
        
        for i, task in enumerate(generation_tasks):
            current_iteration = i + 1
            log_task = log.bind(style=task["style"], seed=task["seed"])
            log_task.info(f"Starting generation {current_iteration}/{generation_count}")

            strategy = get_prompt_strategy(tier_config.client)
            style_payload = strategy.create_group_photo_payload(style=task["style"])
            base_prompt = style_payload.get("prompt", "")

            final_prompt = base_prompt
            enhanced_data = await prompt_enhancer.enhance_prompt(
                image_url=composite_image_url,
                base_prompt=base_prompt
            )
            
            is_enhanced = enhanced_data is not None
            if is_enhanced:
                final_prompt = _construct_final_prompt(base_prompt, enhanced_data)
                log_task.info("Prompt enhanced with structured data", new_prompt_len=len(final_prompt))
                await status.update(_("✍️ Adapting style for your photo..."))
            else:
                log_task.warning("Could not enhance prompt with structured data, using original style prompt.")

            current_payload = pipeline_output.request_payload.copy()
            current_payload.update(style_payload)
            current_payload["prompt"] = final_prompt
            current_payload["seed"] = task["seed"]

            if generation_count > 1:
                await status.update(_("🎨 Generating portrait {current} of {total}...").format(
                    current=current_iteration, total=generation_count
                ))
            else:
                await status.update(_("🎨 Generating your portrait..."))
            
            result, error_meta = await pipeline.run_generation(
                pipeline_output, payload_override=current_payload
            )

            if not result:
                log_task.error("AI service failed for one of the generations", meta=error_meta)
                if current_iteration == generation_count:
                     await status.update(_("There was an issue with the last generation, but here are the previous ones!"))
                     await asyncio.sleep(3)
                continue

            translated_style_name = get_translated_style_name(task["style"])
            caption_text = _("Style: {style_name}").format(style_name=translated_style_name)

            photo = BufferedInputFile(result.image_bytes, f"group_photo_{current_iteration}.png")
            last_sent_message = await bot.send_photo(
                chat_id=chat_id, 
                photo=photo, 
                caption=caption_text
            )

            asyncio.create_task(
                _calculate_and_update_similarity_caption(
                    bot=bot, chat_id=chat_id, message_id=last_sent_message.message_id,
                    original_caption=caption_text, cache_pool=cache_pool, log=log_task,
                    gen_data=gen_data, result_image_bytes=result.image_bytes,
                )
            )
            
            result_image_unique_id = last_sent_message.photo[-1].file_unique_id
            result_file_id = last_sent_message.photo[-1].file_id

            asyncio.create_task(
                GoogleSheetsLogger().log_generation(
                    gen_data=gen_data, result=result, output_image_unique_id=result_image_unique_id
                )
            )
            
            log_entry = generations_repo.GenerationLog(
                request_id=request_id, type=GenerationType.GROUP_PHOTO.value, status="completed",
                quality_level=quality_level, trial_type=trial_type, seed=task["seed"], style=task["style"],
                generation_time_ms=result.generation_time_ms, 
                api_request_payload=result.request_payload,
                api_response_payload=result.response_payload, 
                enhanced_prompt=final_prompt if is_enhanced else None,
                result_image_unique_id=result_image_unique_id,
                result_message_id=last_sent_message.message_id, result_file_id=result_file_id,
                caption=caption_text,
            )
            await generations_repo.create_generation_log(db, log_entry)

            await image_cache.cache_image_bytes(
                result_image_unique_id, result.image_bytes, result.content_type, cache_pool
            )

        await status.delete()

        if not last_sent_message:
             raise RuntimeError("All generation attempts failed.")

        await bot.send_message(
            chat_id, _("What would you like to do next?"), 
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
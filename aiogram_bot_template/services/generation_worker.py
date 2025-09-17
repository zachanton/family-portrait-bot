# aiogram_bot_template/services/generation_worker.py
import asyncio
import random
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
from aiogram_bot_template.services import image_cache, prompt_enhancer
from aiogram_bot_template.services.pipelines.group_photo import GroupPhotoPipeline
from aiogram_bot_template.states.user import Generation
from aiogram_bot_template.utils.status_manager import StatusMessageManager
from aiogram_bot_template.services.prompting.factory import get_prompt_strategy
from aiogram_bot_template.services.prompting.fal_strategy import STYLE_PROMPTS, STYLE_DESCRIPTIONS, get_translated_style_name

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

        await generations_repo.update_generation_request_status(db, request_id, "processing")

        # --- 1. Prepare base data and composite image ---
        db_data = await generations_repo.get_request_details_with_sources(db, request_id)
        if not db_data:
            raise ValueError(f"GenerationRequest with id={request_id} not found in DB.")

        gen_data = {**user_data, **db_data, "type": GenerationType.GROUP_PHOTO.value, "quality_level": quality_level}
        
        pipeline = GroupPhotoPipeline(bot, gen_data, log, status.update, cache_pool)
        pipeline_output = await pipeline.prepare_data()
        
        composite_image_url = pipeline_output.request_payload.get("image_urls", [None])[0]
        if not composite_image_url:
            raise ValueError("Composite image URL could not be determined.")
            
        # --- DEBUG: Send the composite image to the user ---
        if composite_uid := pipeline_output.metadata.get("composite_uid"):
            await _send_debug_image(
                bot=bot,
                chat_id=chat_id,
                redis=cache_pool,
                image_uid=composite_uid,
                caption="DEBUG: Composite image (Identity Source)"
            )

        await status.update(_("✍️ Directing your photoshoot..."))
        chosen_style = 'golden_hour' 
        translated_style_name = get_translated_style_name(chosen_style)
        style_context_for_planner = STYLE_DESCRIPTIONS.get(chosen_style, "A beautiful couple portrait.")

        photoshoot_plan = await prompt_enhancer.get_photoshoot_plan(
            image_url=composite_image_url,
            style_context=style_context_for_planner,
            shot_count=generation_count,
        )

        if not photoshoot_plan:
            log.error("Failed to generate a photoshoot plan. Aborting generation.")
            await status.update(_("Sorry, I couldn't plan the photoshoot. Please try again."))
            await asyncio.sleep(3)
            raise RuntimeError("Photoshoot planning failed.")
        
        log.info("Photoshoot plan created successfully.", plan=photoshoot_plan.model_dump())
        
        master_shot_url = None
        last_sent_message = None
        source_generation_id = None
        strategy = get_prompt_strategy(tier_config.client)

        for i in range(generation_count):
            current_iteration = i + 1
            log_task = log.bind(style=chosen_style, sequence=f"{current_iteration}/{generation_count}")
            
            await status.update(_("🎨 Generating shot {current} of {total}...").format(current=current_iteration, total=generation_count))
            
            current_payload = pipeline_output.request_payload.copy()
            final_prompt: str

            if i == 0:
                log_task.info("Preparing first shot (Master Shot) with a safe, compatible pose.")
                
                wardrobe_text = prompt_enhancer.format_photoshoot_plan_for_prompt(photoshoot_plan, body_part="upper")
                
                style_payload = strategy.create_group_photo_payload(style=chosen_style)
                prompt_template = style_payload.get("prompt", "")
                
                final_prompt = prompt_template.replace("{{PHOTOSHOOT_PLAN_DATA}}", wardrobe_text)
                
                current_payload["image_urls"] = [composite_image_url]
            else:
                log_task.info("Preparing next creative shot.")
                
                if not master_shot_url:
                    log.warning("Master shot URL is not available, ending photoshoot early.")
                    await bot.send_message(chat_id, _("Could not create the first shot, so the photoshoot cannot continue."))
                    break

                wardrobe_text = prompt_enhancer.format_photoshoot_plan_for_prompt(photoshoot_plan, body_part="full")
                pose_details = photoshoot_plan.poses[i-1] 
                pose_text = prompt_enhancer.format_pose_for_prompt(pose_details)

                style_payload = strategy.create_group_photo_next_payload(style=chosen_style)
                prompt_template = style_payload.get("prompt", "")
                
                temp_prompt = prompt_template.replace("{{PHOTOSHOOT_PLAN_DATA}}", wardrobe_text)
                final_prompt = temp_prompt.replace("{{POSE_AND_COMPOSITION_DATA}}", pose_text)
                
                current_payload["image_urls"] = [master_shot_url]
            
            current_payload.update(style_payload)
            current_payload["prompt"] = final_prompt
            current_payload["seed"] = random.randint(1, 1_000_000)
            
            log_task.info("Final prompt prepared for generation", final_prompt=final_prompt)
            
            result, error_meta = await pipeline.run_generation(
                pipeline_output, payload_override=current_payload
            )

            if not result:
                log_task.error("AI service failed for this frame", meta=error_meta)
                if i > 0:
                    await bot.send_message(chat_id, _("Sorry, there was a problem creating the next shot. The photoshoot will end here."))
                break

            caption_text = _("Style: {style_name} (Shot {current}/{total})").format(
                style_name=translated_style_name, current=current_iteration, total=generation_count
            )
            photo = BufferedInputFile(result.image_bytes, f"photoshoot_{current_iteration}.png")
            last_sent_message = await bot.send_photo(chat_id=chat_id, photo=photo, caption=caption_text)

            result_image_unique_id = last_sent_message.photo[-1].file_unique_id
            await image_cache.cache_image_bytes(result_image_unique_id, result.image_bytes, result.content_type, cache_pool)

            if i == 0:
                master_shot_url = image_cache.get_cached_image_proxy_url(result_image_unique_id)

            # --- Log the generation to DB ---
            log_entry = generations_repo.GenerationLog(
                request_id=request_id, type=GenerationType.GROUP_PHOTO.value, status="completed",
                quality_level=quality_level, trial_type=trial_type, seed=current_payload["seed"], style=chosen_style,
                generation_time_ms=result.generation_time_ms,
                api_request_payload=result.request_payload,
                api_response_payload=result.response_payload,
                enhanced_prompt=final_prompt,
                result_image_unique_id=result_image_unique_id,
                result_message_id=last_sent_message.message_id, result_file_id=last_sent_message.photo[-1].file_id,
                caption=caption_text, sequence_index=i, source_generation_id=source_generation_id
            )
            source_generation_id = await generations_repo.create_generation_log(db, log_entry)

        # --- Finalize the flow ---
        await status.delete()

        if not last_sent_message:
             await bot.send_message(chat_id, _("Unfortunately, there was an issue and your photoshoot could not be completed. Please try again with /start."))
             await generations_repo.update_generation_request_status(db, request_id, "failed")
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

# aiogram_bot_template/services/generation_worker.py
import asyncio
import random
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
        
        if composite_uid := pipeline_output.metadata.get("composite_uid"):
            await _send_debug_image(
                bot=bot, chat_id=chat_id, redis=cache_pool,
                image_uid=composite_uid, caption="DEBUG: Composite image (input for AI)",
            )
        
        last_sent_message = None
        
        for i, task in enumerate(generation_tasks):
            current_iteration = i + 1
            log.info(f"Starting generation {current_iteration}/{generation_count}", task=task)

            if generation_count > 1:
                await status.update(_("🎨 Generating portrait {current} of {total}...").format(
                    current=current_iteration, total=generation_count
                ))
            else:
                await status.update(_("🎨 Generating your portrait..."))
            
            strategy = get_prompt_strategy(tier_config.client)
            style_payload = strategy.create_group_photo_payload(style=task["style"])
            
            current_payload = pipeline_output.request_payload.copy()
            current_payload.update(style_payload)
            current_payload["seed"] = task["seed"]

            result, error_meta = await pipeline.run_generation(
                pipeline_output, payload_override=current_payload
            )

            if not result:
                log.error("AI service failed for one of the generations", meta=error_meta, task=task)
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
                generation_time_ms=result.generation_time_ms, api_request_payload=result.request_payload,
                api_response_payload=result.response_payload, result_image_unique_id=result_image_unique_id,
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



        
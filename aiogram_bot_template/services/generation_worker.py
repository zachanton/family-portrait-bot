# aiogram_bot_template/services/generation_worker.py
import asyncio
import random
from contextlib import suppress
from typing import Type

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
from aiogram_bot_template.keyboards.inline import feedback, next_step, child_selection
from aiogram_bot_template.services import image_cache
from aiogram_bot_template.services.pipelines.base import BasePipeline
from aiogram_bot_template.services.pipelines.pair_photo import PairPhotoPipeline
from aiogram_bot_template.services.pipelines.child_generation import ChildGenerationPipeline
from aiogram_bot_template.services.pipelines.family_photo import FamilyPhotoPipeline
from aiogram_bot_template.states.user import Generation
from aiogram_bot_template.utils.status_manager import StatusMessageManager
from aiogram_bot_template.services.prompting.factory import get_prompt_strategy

PIPELINE_MAP: dict[str, Type[BasePipeline]] = {
    GenerationType.PAIR_PHOTO.value: PairPhotoPipeline,
    GenerationType.CHILD_GENERATION.value: ChildGenerationPipeline,
    GenerationType.FAMILY_PHOTO.value: FamilyPhotoPipeline,
}

SEND_DEBUG = True

async def _send_debug_if_enabled(
    bot: Bot, chat_id: int, redis: Redis, uid: str | None, caption: str
):
    """Sends the image to the user if debug mode is enabled in settings."""
    if not SEND_DEBUG or not uid:
        return
    
    try:
        image_bytes, _ = await image_cache.get_cached_image_bytes(uid, redis)
        if image_bytes:
            photo = BufferedInputFile(image_bytes, f"{uid}.jpg")
            await bot.send_photo(chat_id=chat_id, photo=photo, caption=caption)
    except Exception:
        structlog.get_logger(__name__).warning(
            "Failed to send debug image", uid=uid
        )

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
    quality_level = user_data.get("quality_level")
    trial_type = user_data.get("trial_type")
    generation_type = user_data.get("generation_type")

    log = business_logger.bind(req_id=request_id, chat_id=chat_id, type=generation_type)
    db = PostgresConnection(db_pool, logger=log, decode_json=True)
    status = StatusMessageManager(bot, chat_id, status_message_id)

    sent_photo_messages = []

    try:
        if not all([request_id, quality_level is not None, generation_type]):
            raise ValueError("Missing critical data in FSM state for worker.")

        pipeline_class = PIPELINE_MAP.get(generation_type)
        if not pipeline_class:
            raise ValueError(f"No pipeline found for generation type: {generation_type}")

        generation_config = getattr(settings, generation_type)
        tier_config = generation_config.tiers.get(quality_level)
        if not tier_config:
            raise ValueError(f"Tier config not found for type={generation_type}, quality={quality_level}")

        generation_count = tier_config.count
        
        await generations_repo.update_generation_request_status(db, request_id, "processing")

        db_data = await generations_repo.get_request_details_with_sources(db, request_id)
        if not db_data:
            raise ValueError(f"GenerationRequest id={request_id} not found.")

        gen_data = {**user_data, **db_data, 'type': generation_type}
        
        pipeline = pipeline_class(bot, gen_data, log, status.update, cache_pool)
        pipeline_output = await pipeline.prepare_data()

        await _send_debug_if_enabled(
            bot=bot, chat_id=chat_id, redis=cache_pool,
            uid=pipeline_output.metadata.get("composite_uid"),
            caption="[DEBUG] This is the composite image sent to the AI."
        )

        await _send_debug_if_enabled(
            bot=bot, chat_id=chat_id, redis=cache_pool,
            uid=pipeline_output.metadata.get("mom_uid"),
            caption="[DEBUG] This is the mom image sent to the AI."
        )

        await _send_debug_if_enabled(
            bot=bot, chat_id=chat_id, redis=cache_pool,
            uid=pipeline_output.metadata.get("dad_uid"),
            caption="[DEBUG] This is the dad image sent to the AI."
        )

        await _send_debug_if_enabled(
            bot=bot, chat_id=chat_id, redis=cache_pool,
            uid=pipeline_output.metadata.get("child_uid", None),
            caption="[DEBUG] This is the child image sent to the AI."
        )

        for i in range(generation_count):
            current_iteration = i + 1
            log_task = log.bind(sequence=f"{current_iteration}/{generation_count}")
            
            await status.update(_("🎨 Generating image {current} of {total}...").format(
                current=current_iteration, total=generation_count
            ))

            payload_override = pipeline_output.request_payload.copy()
            payload_override["seed"] = random.randint(1, 1_000_000)

            log_task.info(
                "Final prompt for image generation model",
                prompt_text=payload_override.get("prompt", "Prompt not found")
            )

            result, error_meta = await pipeline.run_generation(
                pipeline_output, payload_override=payload_override
            )

            if not result:
                log_task.error("AI service failed for this frame", meta=error_meta)
                continue

            photo = BufferedInputFile(result.image_bytes, f"generation_{current_iteration}.png")

            log_entry_draft = generations_repo.GenerationLog(
                request_id=request_id, type=generation_type, status="completed",
                quality_level=quality_level, trial_type=trial_type, seed=payload_override["seed"],
                generation_time_ms=result.generation_time_ms,
                api_request_payload=result.request_payload, api_response_payload=result.response_payload,
                caption=pipeline_output.caption
            )
            generation_id = await generations_repo.create_generation_log(db, log_entry_draft)

            reply_markup = None
            if generation_type == GenerationType.CHILD_GENERATION.value:
                reply_markup = child_selection.continue_with_image_kb(
                    generation_id=generation_id,
                    request_id=request_id
                )

            last_sent_message = await bot.send_photo(
                chat_id=chat_id, photo=photo, caption=pipeline_output.caption, reply_markup=reply_markup
            )

            unique_id = last_sent_message.photo[-1].file_unique_id
            await image_cache.cache_image_bytes(unique_id, result.image_bytes, result.content_type, cache_pool)
            
            sql_update_log = """
                UPDATE generations
                SET result_image_unique_id = $1, result_message_id = $2, result_file_id = $3
                WHERE id = $4;
            """
            await db.execute(sql_update_log, (
                unique_id, last_sent_message.message_id, last_sent_message.photo[-1].file_id, generation_id
            ))

            sent_photo_messages.append({"message_id": last_sent_message.message_id, "generation_id": generation_id})

        await status.delete()

        if not sent_photo_messages:
            await bot.send_message(
                chat_id, 
                _("Unfortunately, I couldn't create an image this time. Please try again with /start.")
            )
            await generations_repo.update_generation_request_status(db, request_id, "failed")
            await state.clear()
            return

        await generations_repo.update_generation_request_status(db, request_id, "completed")
        
        # --- ИЗМЕНЕНИЕ ЗДЕСЬ ---
        if generation_type == GenerationType.CHILD_GENERATION.value:
            # Send the separate, clear call-to-action message.
            next_step_msg = await bot.send_message(
                chat_id, 
                _("✨ Your AI generations are ready!\n\n"
                  "Please select one of the children above to continue, or press /start to begin again."),
            )

            # Store all relevant message IDs in the state for future cleanup.
            await state.update_data(
                photo_message_ids=[m["message_id"] for m in sent_photo_messages],
                next_step_message_id=next_step_msg.message_id # Save the ID of the instruction message
            )
            await state.set_state(Generation.waiting_for_next_action)

        elif generation_type in [GenerationType.PAIR_PHOTO.value, GenerationType.FAMILY_PHOTO.value]:
            await bot.send_message(
                chat_id, 
                _("Your photoshoot is complete! What's next?"),
                reply_markup=next_step.get_next_step_keyboard("continue", request_id)
            )
            await state.set_state(Generation.waiting_for_next_action)
            
        else:
            await bot.send_message(
                chat_id, _("Done! Use /start to begin a new session."),
            )
            await state.clear()

    except Exception:
        log.exception("An unhandled error occurred in the generation worker.")
        if status_message_id:
            with suppress(TelegramBadRequest):
                await status.delete()
        await bot.send_message(
            chat_id, _("😔 An unexpected error occurred. Please try again with /start.")
        )
        if request_id:
            await generations_repo.update_generation_request_status(db, request_id, "failed_internal")
    finally:
        current_state = await state.get_state()
        if current_state and current_state not in [
            Generation.waiting_for_next_action, 
            Generation.waiting_for_feedback,
            Generation.child_selected,
        ]:
            await state.clear()
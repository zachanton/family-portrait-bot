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
from aiogram_bot_template.keyboards.inline import feedback, next_step
# --- NEW: Import the new keyboard ---
from aiogram_bot_template.keyboards.inline import child_selection
from aiogram_bot_template.services import image_cache
from aiogram_bot_template.services.pipelines.base import BasePipeline
from aiogram_bot_template.services.pipelines.group_photo import GroupPhotoPipeline
# --- NEW: Import the new pipeline ---
from aiogram_bot_template.services.pipelines.child_generation import ChildGenerationPipeline
from aiogram_bot_template.states.user import Generation
from aiogram_bot_template.utils.status_manager import StatusMessageManager
from aiogram_bot_template.services.prompting.factory import get_prompt_strategy

# --- NEW: A map to select the correct pipeline ---
PIPELINE_MAP: dict[str, Type[BasePipeline]] = {
    GenerationType.GROUP_PHOTO.value: GroupPhotoPipeline,
    GenerationType.CHILD_GENERATION.value: ChildGenerationPipeline,
}

async def _send_debug_composite_if_enabled(
    bot: Bot, chat_id: int, redis: Redis, composite_uid: str | None, caption: str
):
    """Sends the composite image to the user if debug mode is enabled in settings."""
    if not settings.bot.send_debug_composites or not composite_uid:
        return
    
    try:
        image_bytes, _ = await image_cache.get_cached_image_bytes(composite_uid, redis)
        if image_bytes:
            photo = BufferedInputFile(image_bytes, f"{composite_uid}.jpg")
            await bot.send_photo(chat_id=chat_id, photo=photo, caption=caption)
    except Exception as e:
        # Use a proper logger to avoid crashing the worker
        structlog.get_logger(__name__).warning(
            "Failed to send debug composite image",
            uid=composite_uid,
            error=str(e)
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

    generation_id = None
    # --- NEW: List to store message data ---
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

        gen_data = {**user_data, **db_data}
        gen_data['type'] = generation_type
        
        pipeline = pipeline_class(bot, gen_data, log, status.update, cache_pool)
        pipeline_output = await pipeline.prepare_data()

        await _send_debug_composite_if_enabled(
            bot=bot,
            chat_id=chat_id,
            redis=cache_pool,
            composite_uid=pipeline_output.metadata.get("composite_uid"),
            caption="[DEBUG] This is the composite image sent to the AI."
        )

        await _send_debug_composite_if_enabled(
            bot=bot,
            chat_id=chat_id,
            redis=cache_pool,
            composite_uid=pipeline_output.metadata.get("faces_only_uid"),
            caption="[DEBUG] This is the faces_only image sent to the AI."
        )

        loop_driver = [None] * generation_count

        for i, item in enumerate(loop_driver):
            current_iteration = i + 1
            log_task = log.bind(sequence=f"{current_iteration}/{generation_count}")
            
            await status.update(_("🎨 Generating image {current} of {total}...").format(
                current=current_iteration, total=generation_count
            ))

            payload_override = pipeline_output.request_payload.copy()
            
            if generation_type == GenerationType.CHILD_GENERATION.value and item:
                strategy = get_prompt_strategy(tier_config.client)
                child_payload = strategy.create_child_generation_payload(
                    description=item,
                    child_gender=user_data["child_gender"],
                    child_age=user_data["child_age"],
                    child_resemblance=user_data["child_resemblance"]
                )
                payload_override.update(child_payload)
            
            payload_override["seed"] = random.randint(1, 1_000_000)

            final_prompt = payload_override.get("prompt", "Prompt not found in payload")
            log_task.info(
                "Final prompt for image generation model",
                prompt_text=final_prompt
            )

            result, error_meta = await pipeline.run_generation(
                pipeline_output, payload_override=payload_override
            )

            if not result:
                log_task.error("AI service failed for this frame", meta=error_meta)
                if i > 0:
                    await bot.send_message(chat_id, _("Sorry, there was a problem creating the next image."))
                continue

            photo = BufferedInputFile(result.image_bytes, f"generation_{current_iteration}.png")
            last_sent_message = await bot.send_photo(chat_id=chat_id, photo=photo, caption=pipeline_output.caption)

            unique_id = last_sent_message.photo[-1].file_unique_id
            await image_cache.cache_image_bytes(unique_id, result.image_bytes, result.content_type, cache_pool)

            log_entry = generations_repo.GenerationLog(
                request_id=request_id, type=generation_type, status="completed",
                quality_level=quality_level, trial_type=trial_type, seed=payload_override["seed"],
                generation_time_ms=result.generation_time_ms,
                api_request_payload=result.request_payload, api_response_payload=result.response_payload,
                result_image_unique_id=unique_id, result_message_id=last_sent_message.message_id,
                result_file_id=last_sent_message.photo[-1].file_id, caption=pipeline_output.caption
            )
            generation_id = await generations_repo.create_generation_log(db, log_entry)
            
            # --- NEW: Store message and generation ID ---
            sent_photo_messages.append({
                "message_id": last_sent_message.message_id,
                "generation_id": generation_id
            })

        await status.delete()

        if not sent_photo_messages:
            # Handle case where all generation attempts failed
            await bot.send_message(
                chat_id, 
                _("Unfortunately, I couldn't create an image this time. Please try again with /start.")
            )
            await generations_repo.update_generation_request_status(db, request_id, "failed")
            await state.clear()
            return

        await generations_repo.update_generation_request_status(db, request_id, "completed")
        
        if generation_type == GenerationType.CHILD_GENERATION.value:
            # 1. Send the final "next step" message with updated text
            next_step_msg = await bot.send_message(
                chat_id, 
                _("Your potential children are ready!\n\nPlease select one of the images above to proceed, or choose an action from the menu below."),
                reply_markup=next_step.get_next_step_keyboard("continue", request_id)
            )
            next_step_message_id = next_step_msg.message_id

            # 2. Add "Continue" buttons to each photo message
            for msg_data in sent_photo_messages:
                with suppress(TelegramBadRequest):
                    await bot.edit_message_reply_markup(
                        chat_id=chat_id,
                        message_id=msg_data["message_id"],
                        reply_markup=child_selection.continue_with_image_kb(
                            generation_id=msg_data["generation_id"],
                            request_id=request_id,
                            next_step_message_id=next_step_message_id
                        )
                    )
            
            # 3. Store all relevant message IDs in FSM state for cleanup
            await state.update_data(
                photo_message_ids=[m["message_id"] for m in sent_photo_messages],
                next_step_message_id=next_step_message_id
            )
            await state.set_state(Generation.waiting_for_next_action)

        elif generation_type == GenerationType.GROUP_PHOTO.value:
            # --- OLD LOGIC for Group Photo (and future features) ---
            last_sent_message = await bot.send_message(chat_id=chat_id, text="...") # You need to define how to get the last message here
            if generation_count == 1 and settings.collect_feedback:
                await last_sent_message.edit_reply_markup(
                    reply_markup=feedback.feedback_kb(generation_id, request_id, "continue")
                )
                await state.set_state(Generation.waiting_for_feedback)
            else:
                await bot.send_message(
                    chat_id, 
                    _("Your photoshoot is complete! What's next?"),
                    reply_markup=next_step.get_next_step_keyboard("continue", request_id)
                )
                await state.set_state(Generation.waiting_for_next_action)
        else:
             # Default fallback
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
            Generation.waiting_for_feedback
        ]:
            await state.clear()
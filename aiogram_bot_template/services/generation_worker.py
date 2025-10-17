# aiogram_bot_template/services/generation_worker.py
import asyncio
import random
from contextlib import suppress
from typing import Type, Set

import asyncpg
import structlog
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile
from aiogram.utils.i18n import gettext as _
from redis.asyncio import Redis

from aiogram_bot_template.data.constants import (
    GenerationType,
)
from aiogram_bot_template.data.settings import settings
from aiogram_bot_template.db.db_api.storages import PostgresConnection
from aiogram_bot_template.db.repo import generations as generations_repo
from aiogram_bot_template.keyboards.inline import (
    child_selection, family_selection, pair_selection, session_actions
)
from aiogram_bot_template.services import image_cache
from aiogram_bot_template.services.pipelines.base import BasePipeline
from aiogram_bot_template.services.pipelines.child_generation_pipeline.child_generation import ChildGenerationPipeline
from aiogram_bot_template.services.pipelines.family_photo_pipeline.family_photo import FamilyPhotoPipeline
from aiogram_bot_template.services.pipelines.pair_photo_pipeline.pair_photo import PairPhotoPipeline
from aiogram_bot_template.states.user import Generation
from aiogram_bot_template.utils.status_manager import StatusMessageManager
from aiogram_bot_template.services.photo_processing_manager import PhotoProcessingManager


PIPELINE_MAP: dict[str, Type[BasePipeline]] = {
    GenerationType.CHILD_GENERATION.value: ChildGenerationPipeline,
    GenerationType.FAMILY_PHOTO.value: FamilyPhotoPipeline,
    GenerationType.PAIR_PHOTO.value: PairPhotoPipeline,
}

SEND_DEBUG = True

async def _send_debug_if_enabled(
    bot: Bot, chat_id: int, redis: Redis, uid: str | None, caption: str
):
    """Sends the image to the user if debug mode is enabled in settings."""
    if not SEND_DEBUG or not uid:
        return
    
    try:
        image_bytes, a = await image_cache.get_cached_image_bytes(uid, redis)
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
    photo_manager: PhotoProcessingManager,
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
        
        pipeline = pipeline_class(
            bot, gen_data, log, status.update, cache_pool, photo_manager=photo_manager
        )
        pipeline_output = await pipeline.prepare_data()

        if "mom_profile_uid" not in user_data:
            session_uids = {
                "mom_profile_uid": pipeline_output.metadata.get("mom_profile_uid"),
                "dad_profile_uid": pipeline_output.metadata.get("dad_profile_uid"),
                "mom_front_dad_front_uid": pipeline_output.metadata.get("mom_front_dad_front_uid"),
                "mom_front_dad_side_uid": pipeline_output.metadata.get("mom_front_dad_side_uid"),
                "dad_front_mom_side_uid": pipeline_output.metadata.get("dad_front_mom_side_uid"),
                "parent_front_side_uid": pipeline_output.metadata.get("parent_front_side_uid"),
            }
            if all(session_uids.values()):
                await state.update_data(**session_uids)
                log.info("Saved parent visual UIDs to FSM state for session.", uids=session_uids)
            elif generation_type != GenerationType.FAMILY_PHOTO.value:
                 log.warning("Could not find all required session UIDs in pipeline metadata to save.")

        await _send_debug_if_enabled(
            bot=bot, chat_id=chat_id, redis=cache_pool,
            uid=pipeline_output.metadata.get("mom_collage_uid"),
            caption="[DEBUG] mom_collage_uid."
        )
        await _send_debug_if_enabled(
            bot=bot, chat_id=chat_id, redis=cache_pool,
            uid=pipeline_output.metadata.get("mom_profile_uid"),
            caption="[DEBUG] mom_profile_uid."
        )
        await _send_debug_if_enabled(
            bot=bot, chat_id=chat_id, redis=cache_pool,
            uid=pipeline_output.metadata.get("dad_collage_uid"),
            caption="[DEBUG] dad_collage_uid."
        )
        await _send_debug_if_enabled(
            bot=bot, chat_id=chat_id, redis=cache_pool,
            uid=pipeline_output.metadata.get("dad_profile_uid"),
            caption="[DEBUG] dad_profile_uid."
        )

        for i_uid, uid in enumerate(pipeline_output.metadata.get("processed_uids")):
            await _send_debug_if_enabled(
                bot=bot, chat_id=chat_id, redis=cache_pool,
                uid=uid,
                caption=f"[DEBUG] {i_uid} processed uid (final input to AI)."
            )
        
        completed_prompts = pipeline_output.metadata.get("completed_prompts", [])
        image_reference_list = pipeline_output.metadata.get("image_reference_list", [])

        for i in range(generation_count):
            current_iteration = i + 1
            log_task = log.bind(sequence=f"{current_iteration}/{generation_count}")
            
            await status.update(_("🎨 Painting portrait {current} of {total}...").format(
                current=current_iteration, total=generation_count
            ))

            payload_override = pipeline_output.request_payload.copy()

            if completed_prompts and i < len(completed_prompts):
                final_prompt = completed_prompts[i]
            else:
                log_task.error("Completed prompt missing for this iteration.", gen_type=generation_type)
                continue

            if image_reference_list and i < len(image_reference_list):
                image_reference = image_reference_list[i]
            else:
                log_task.error("Image reference missing for this iteration.", gen_type=generation_type)
                continue
                
            payload_override["prompt"] = final_prompt
            payload_override["image_urls"] = [ image_reference ]
            payload_override["seed"] = random.randint(1, 1_000_000)

            log.info("Final prompt: ", final_prompt=payload_override["prompt"])

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
                caption=pipeline_output.caption,
                enhanced_prompt=final_prompt
            )
            generation_id = await generations_repo.create_generation_log(db, log_entry_draft)

            reply_markup = None
            if generation_type == GenerationType.CHILD_GENERATION.value:
                reply_markup = child_selection.continue_with_image_kb(generation_id=generation_id, request_id=request_id)
            elif generation_type == GenerationType.FAMILY_PHOTO.value:
                reply_markup = family_selection.continue_with_family_photo_kb(generation_id=generation_id, request_id=request_id)
            elif generation_type == GenerationType.PAIR_PHOTO.value:
                reply_markup = pair_selection.continue_with_pair_photo_kb(generation_id=generation_id, request_id=request_id)

            last_sent_message = await bot.send_photo(
                chat_id=chat_id, photo=photo, caption=pipeline_output.caption, reply_markup=reply_markup
            )

            unique_id = last_sent_message.photo[-1].file_unique_id
            await image_cache.cache_image_bytes(unique_id, result.image_bytes, result.content_type, cache_pool)
            
            sql_update_log = "UPDATE generations SET result_image_unique_id = $1, result_message_id = $2, result_file_id = $3 WHERE id = $4;"
            await db.execute(sql_update_log, (unique_id, last_sent_message.message_id, last_sent_message.photo[-1].file_id, generation_id))

            sent_photo_messages.append({"message_id": last_sent_message.message_id, "generation_id": generation_id})

        await status.delete()

        if not sent_photo_messages:
            await bot.send_message(chat_id, _("Oh dear, the AI seems to be having a creative block! I couldn't create an image this time. Please use /start to try again."))
            await generations_repo.update_generation_request_status(db, request_id, "failed")
            await state.clear()
            return

        await generations_repo.update_generation_request_status(db, request_id, "completed")
        
        current_data = await state.get_data()
        generated_in_session: Set[str] = set(current_data.get("generated_in_session", []))
        generated_in_session.add(generation_type)
        await state.update_data(generated_in_session=list(generated_in_session))
        
        existing_photo_ids = current_data.get("photo_message_ids", [])
        new_photo_ids = [m["message_id"] for m in sent_photo_messages]
        all_photo_ids = existing_photo_ids + new_photo_ids
        
        await state.update_data(photo_message_ids=all_photo_ids)
        
        session_actions_msg = await bot.send_message(
            chat_id, 
            _("✨ Your portraits are ready!\n\n"
              "Which one is your favorite? Tap the button below your chosen image, or select another action."),
            reply_markup=session_actions.session_actions_kb(generated_in_session)
        )
        await state.update_data(next_step_message_id=session_actions_msg.message_id)
        
        await state.set_state(Generation.waiting_for_next_action)

    except Exception:
        log.exception("An unhandled error occurred in the generation worker.")
        if status_message_id:
            with suppress(TelegramBadRequest):
                await status.delete()
        await bot.send_message(chat_id, _("😔 An unexpected error occurred on our end. Please try again with /start."))
        if request_id:
            await generations_repo.update_generation_request_status(db, request_id, "failed_internal")
    finally:
        current_state = await state.get_state()
        if current_state and current_state not in [
            Generation.waiting_for_next_action, 
        ]:
            await state.clear()
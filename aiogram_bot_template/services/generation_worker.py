# File: aiogram_bot_template/services/generation_worker.py
import json
import uuid
from contextlib import suppress
import asyncio
import random
import aiohttp

import asyncpg
import structlog
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile
from aiogram.utils.i18n import gettext as _
from redis.asyncio import Redis

from aiogram_bot_template.data.constants import GenerationType, SessionContextType
from aiogram_bot_template.data.settings import settings
from aiogram_bot_template.db.db_api.storages import PostgresConnection
from aiogram_bot_template.db.repo import generations as generations_repo
from aiogram_bot_template.keyboards.inline import next_step, feedback
from aiogram_bot_template.services import image_cache, image_generation_service as ai_service
from aiogram_bot_template.services.llm_invokers import VisionService
from aiogram_bot_template.services.pipelines.base import PipelineOutput
from aiogram_bot_template.services.pipelines.child_generation import ChildGenerationPipeline
from aiogram_bot_template.services.pipelines.image_edit import ImageEditPipeline
from aiogram_bot_template.services.pipelines.upscale import UpscalePipeline
from aiogram_bot_template.services.pipelines.group_photo import GroupPhotoPipeline
from aiogram_bot_template.services.pipelines.group_photo_edit import GroupPhotoEditPipeline
from aiogram_bot_template.states.user import Generation
from aiogram_bot_template.utils.status_manager import StatusMessageManager
from aiogram_bot_template.utils.parameter_parser import extract_latest_parameters
from aiogram_bot_template.dto.post_generation_context import PostGenerationContext, GenerationContext
from aiogram_bot_template.dto.facial_features import ImageDescription
from aiogram_bot_template.services.google_sheets_logger import GoogleSheetsLogger


PIPELINE_REGISTRY = {
    GenerationType.CHILD_GENERATION: ChildGenerationPipeline,
    GenerationType.IMAGE_EDIT: ImageEditPipeline,
    GenerationType.UPSCALE: UpscalePipeline,
    GenerationType.GROUP_PHOTO: GroupPhotoPipeline,
    GenerationType.GROUP_PHOTO_EDIT: GroupPhotoEditPipeline,
}


async def _update_status_periodically(bot: Bot, chat_id: int, message_id: int, stop_event: asyncio.Event) -> None:
    messages = [
        _("🎨 Applying final touches..."),
        _("✨ Polishing the details..."),
        _("🔮 Consulting the AI spirits..."),
        _("⏳ Almost there..."),
    ]
    last_message = ""
    while not stop_event.is_set():
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=15)
        except asyncio.TimeoutError:
            new_message = random.choice([m for m in messages if m != last_message] or messages)
            last_message = new_message
            with suppress(TelegramBadRequest):
                await bot.edit_message_text(text=new_message, chat_id=chat_id, message_id=message_id)


async def run_generation_worker(  # noqa: PLR0913, PLR0917
    bot: Bot,
    user_id: int,
    chat_id: int,
    status_message_id: int,
    db_pool: asyncpg.Pool,
    business_logger: structlog.typing.FilteringBoundLogger,
    cache_pool: Redis,
    state: FSMContext,
) -> None:
    user_data = await state.get_data()
    request_id = user_data.get("request_id")

    log = business_logger.bind(req_id=request_id, user_id=user_id, chat_id=chat_id)
    db = PostgresConnection(db_pool, logger=log, decode_json=True)
    status = StatusMessageManager(bot, chat_id, status_message_id)

    vision_service = VisionService()

    periodic_updater_task = None
    stop_event = asyncio.Event()

    try:
        if not request_id:
            raise ValueError("request_id not found in FSM state for worker.")

        db_data = await generations_repo.get_request_details_with_sources(db, request_id)
        if not db_data:
            raise ValueError(f"GenerationRequest with id={request_id} not found in DB.")

        log.info(
            "Worker preparing data",
            user_data_from_fsm=user_data,
            db_data_loaded=db_data,
        )

        params_raw = db_data.get("request_parameters")
        params_from_db = extract_latest_parameters(params_raw)
        gen_data_for_pipeline = {**user_data, **db_data, **params_from_db}

        log.info("Worker data merged", final_gen_data=gen_data_for_pipeline)

        if "generation_type" in gen_data_for_pipeline:
            gen_data_for_pipeline["type"] = gen_data_for_pipeline["generation_type"]
        if "quality" in gen_data_for_pipeline:
            gen_data_for_pipeline["quality_level"] = gen_data_for_pipeline["quality"]

        await generations_repo.update_generation_request_status(db, request_id, "processing")

        gen_type = GenerationType(gen_data_for_pipeline.get("type"))
        pipeline_class = PIPELINE_REGISTRY.get(gen_type)
        if not pipeline_class:
            raise NotImplementedError(f"No pipeline implemented for type: {gen_type}")

        pipeline = pipeline_class(bot, gen_data_for_pipeline, log, status.update, cache_pool)
        pipeline_output = await pipeline.prepare_data()

        periodic_updater_task = asyncio.create_task(
            _update_status_periodically(bot, chat_id, status_message_id, stop_event)
        )

        result, error_meta = await pipeline.run_generation(pipeline_output)

        stop_event.set()
        await periodic_updater_task
        periodic_updater_task = None

        if not result:
            raise RuntimeError(f"AI service failed: {error_meta}")

        child_description: ImageDescription | None = None

        if gen_type in [GenerationType.CHILD_GENERATION, GenerationType.IMAGE_EDIT]:
            await status.update(_("Analyzing result... 🔎"))
            child_description = await vision_service.analyze_face(
                image_bytes=result.image_bytes,
                content_type=result.content_type
            )
            log.info("Result analysis complete.", description_found=child_description is not None)
        else:
            log.info("Skipping result analysis for this generation type.", type=gen_type.value)
            # For types that don't get analyzed, we must preserve the existing description
            if existing_desc_data := user_data.get("child_description"):
                try:
                    child_description = ImageDescription.model_validate(existing_desc_data)
                    log.info("Successfully reused existing child description.")
                except Exception:
                    log.warning("Could not re-validate existing child description during reuse.")
            else:
                log.warning("No existing child description found to reuse.")

        await status.delete()

        await _handle_successful_generation(
            bot, chat_id, request_id, gen_data_for_pipeline, result, db, cache_pool, log, pipeline_output, state,
            child_description=child_description
        )

    except (RuntimeError, aiohttp.ClientError, asyncio.TimeoutError) as e:
        log.warning("A recoverable AI or network error occurred.", exc_info=e)
        if status_message_id:
            await status.delete()
        await bot.send_message(chat_id, _("😔 Oh, it seems I need a short break... My AI circuits are a bit tired. Please try again in a couple of minutes!"))
        if request_id:
            await generations_repo.update_generation_request_status(db, request_id, "failed_downstream")

    except Exception:
        log.exception("An unhandled error occurred in the generation worker.")
        if status_message_id:
            await status.delete()
        await bot.send_message(chat_id, _("😔 An unexpected error occurred on our side. Please try again."))
        if request_id:
            await generations_repo.update_generation_request_status(db, request_id, "failed_internal")

    finally:
        if periodic_updater_task:
            stop_event.set()
            with suppress(asyncio.CancelledError):
                await periodic_updater_task


async def _handle_successful_generation(
    bot: Bot,
    chat_id: int,
    request_id: int,
    gen_data: dict,
    result: ai_service.GenerationResult,
    db: PostgresConnection,
    cache_pool: Redis,
    log: structlog.typing.FilteringBoundLogger,
    pipeline_output: PipelineOutput,
    state: FSMContext,
    child_description: ImageDescription | None,
) -> None:
    user_data = await state.get_data()
    root_request_id = user_data.get("root_request_id")
    
    gen_type = GenerationType(gen_data.get("type"))
    image_bytes = result.image_bytes
    final_caption = pipeline_output.caption
    
    # 1. Determine the context for the NEXT keyboard
    next_session_context: SessionContextType
    previous_context_str = user_data.get("session_context")
    previous_context = SessionContextType(previous_context_str) if previous_context_str else None

    # --- START OF FINAL REFACTORING ---

    if gen_type == GenerationType.CHILD_GENERATION:
        next_session_context = SessionContextType.CHILD_GENERATION
    elif gen_type == GenerationType.GROUP_PHOTO:
        next_session_context = SessionContextType.GROUP_PHOTO
    elif gen_type == GenerationType.IMAGE_EDIT:
        next_session_context = SessionContextType.EDITED_CHILD
    elif gen_type == GenerationType.GROUP_PHOTO_EDIT:
        next_session_context = SessionContextType.EDITED_GROUP_PHOTO
    elif gen_type == GenerationType.UPSCALE:
        next_session_context = previous_context or SessionContextType.CHILD_GENERATION # Fallback
        log.info("Upscale detected. Reusing previous session context.", context=next_session_context.value)
    else:
        next_session_context = SessionContextType.UNKNOWN
    
    sent_message = None
    if gen_type == GenerationType.UPSCALE:
        document = BufferedInputFile(image_bytes, "hd_result.png")
        sent_message = await bot.send_document(chat_id=chat_id, document=document, caption=final_caption)
    else:
        photo = BufferedInputFile(image_bytes, "generated.png")
        sent_message = await bot.send_photo(chat_id=chat_id, photo=photo, caption=final_caption)
    
    result_image_unique_id = sent_message.photo[-1].file_unique_id if sent_message.photo else sent_message.document.file_unique_id
    result_file_id = sent_message.photo[-1].file_id if sent_message.photo else sent_message.document.file_id

    sheets_logger = GoogleSheetsLogger()
    asyncio.create_task(
        sheets_logger.log_generation(
            gen_data=gen_data,
            result=result,
            output_image_unique_id=result_image_unique_id,
        )
    )
    
    continue_key = uuid.uuid4().hex[:16]
    control_message_text = _("What would you like to do next?")
    
    # Call the refactored keyboard function with the determined context
    reply_markup = next_step.get_next_step_keyboard(
        context=next_session_context, 
        continue_key=continue_key, 
        request_id=request_id,
    )
    
    if settings.collect_feedback:
        control_message_text = _("Did you like the result?")
        reply_markup = feedback.feedback_kb(0, request_id, continue_key)
    
    new_control_message = await bot.send_message(chat_id, control_message_text, reply_markup=reply_markup)

    final_parent_descriptions = (
        pipeline_output.metadata.get("parent_descriptions") if pipeline_output.metadata 
        else user_data.get("parent_descriptions")
    )

    # Prepare and save the full generation record to the DB, including the next step context.
    context_to_save = GenerationContext(
        parent_descriptions=final_parent_descriptions,
        child_description=child_description,
        session_context=next_session_context 
    )
    context_metadata = context_to_save.model_dump(exclude_none=True)

    log_entry = generations_repo.GenerationLog(
        request_id=request_id, type=gen_type.value, status="completed", quality_level=gen_data.get("quality"),
        prompt_payload=json.loads(gen_data.get("prompt", "{}")) if gen_data.get("prompt") else None,
        trial_type=gen_data.get("trial_type"), seed=result.request_payload.get("seed"),
        generation_time_ms=result.generation_time_ms, api_request_payload=result.request_payload,
        api_response_payload=result.response_payload, result_image_unique_id=result_image_unique_id,
        result_message_id=sent_message.message_id, result_file_id=result_file_id,
        caption=final_caption, control_message_id=new_control_message.message_id,
        context_metadata=context_metadata,
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
    await image_cache.cache_image_bytes(result_image_unique_id, image_bytes, result.content_type, cache_pool)
    
    generation_details = await generations_repo.get_generation_details(db, generation_id)
    context_to_store = PostGenerationContext.from_db_record(generation_details)
    await cache_pool.set(f"continue_edit:{continue_key}", context_to_store.model_dump_json(), ex=86400)
    
    await state.clear()
    current_state = Generation.waiting_for_next_action if not settings.collect_feedback else Generation.waiting_for_feedback
    await state.set_state(current_state)
    await state.update_data(
        request_id=request_id, active_generation_id=generation_id,
        active_photo_message_id=sent_message.message_id, active_control_message_id=new_control_message.message_id,
        feedback_continue_key=continue_key, feedback_generation_id=generation_id,
        feedback_request_id=request_id,
        session_context=next_session_context.value,
        continue_key=continue_key, root_request_id=root_request_id,
        # Ensure the full context is restored to the FSM for the next step
        parent_descriptions=context_to_store.context.parent_descriptions,
        child_description=context_to_store.context.child_description.model_dump() if context_to_store.context.child_description else None,
    )

    log.info(
        "Worker finished successfully. New active session created.",
        new_active_gen_id=generation_id, new_active_msg_id=new_control_message.message_id
    )
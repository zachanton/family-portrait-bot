# aiogram_bot_template/services/pipelines/base.py
from abc import ABC, abstractmethod
from typing import Any
import structlog
from aiogram import Bot
from pydantic import BaseModel
from redis.asyncio import Redis
from aiogram.utils.i18n import gettext as _

from aiogram_bot_template.data.settings import settings
from aiogram_bot_template.services import image_generation_service as ai_service
from aiogram_bot_template.services.clients import factory as ai_client_factory
from aiogram_bot_template.data.constants import GenerationType


class PipelineOutput(BaseModel):
    """Data structure that each pipeline's prepare_data must return."""
    request_payload: dict[str, Any]
    caption: str
    metadata: dict[str, Any] | None = None


class BasePipeline(ABC):
    """Abstract base class for a generation pipeline."""

    def __init__(
        self,
        bot: Bot,
        gen_data: dict,
        log: structlog.typing.FilteringBoundLogger,
        update_status_func: callable,
        cache_pool: Redis,
    ) -> None:
        self.bot = bot
        self.gen_data = gen_data
        self.log = log
        self.update_status_func = update_status_func
        self.cache_pool = cache_pool

    @abstractmethod
    async def prepare_data(self) -> PipelineOutput:
        """
        Prepares all necessary data for the AI request.
        Must be implemented by subclasses.
        """
        raise NotImplementedError

    async def run_generation(
        self,
        pipeline_output: PipelineOutput
    ) -> tuple[ai_service.GenerationResult | None, dict | None]:
        """
        Selects the AI client, adapts the payload based on config, and runs generation.
        """
        await self.update_status_func(_("Generating final portrait... 🎨"))

        gen_type_enum = GenerationType(self.gen_data["type"])
        quality_level = self.gen_data["quality_level"]

        generation_config = getattr(settings, gen_type_enum.value)
        tier_config = generation_config.tiers.get(quality_level)
        if not tier_config:
            raise ValueError(f"No config found for {gen_type_enum.value} tier {quality_level}")

        generation_ai_client, model_name = ai_client_factory.get_ai_client_and_model(
            generation_type=gen_type_enum, quality=quality_level
        )
        
        payload = pipeline_output.request_payload.copy()
        
        result, error_meta = await ai_service.generate_image_with_reference(
            payload,
            generation_ai_client,
            status_callback=self.update_status_func,
        )

        return result, error_meta
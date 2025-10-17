# aiogram_bot_template/services/pipelines/image_edit_pipeline/image_edit.py
from aiogram.utils.i18n import gettext as _
import asyncpg
import structlog

from aiogram_bot_template.db.db_api.storages import PostgresConnection
from aiogram_bot_template.data.settings import settings
from aiogram_bot_template.data.constants import GenerationType
from aiogram_bot_template.services import image_cache
from ..base import BasePipeline, PipelineOutput
from .edit_default import PROMPT_IMAGE_EDIT_DEFAULT
from aiogram_bot_template.services.photo_processing_manager import PhotoProcessingManager


class ImageEditPipeline(BasePipeline):
    """
    Pipeline for editing an existing generated image based on a user's text prompt.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def prepare_data(self) -> PipelineOutput:
        """
        Prepares data for the image edit generation.
        """
        await self.update_status_func(_("Preparing your image for editing..."))

        source_generation_id = self.gen_data.get("source_generation_id")
        user_prompt = self.gen_data.get("user_prompt")

        if not source_generation_id or not user_prompt:
            raise ValueError("Missing source generation ID or user prompt for editing.")

        db = PostgresConnection(self.db_pool, self.log)
        sql = "SELECT result_image_unique_id FROM generations WHERE id = $1"
        result = await db.fetchrow(sql, (source_generation_id,))

        if not result or not result.data or not result.data.get("result_image_unique_id"):
            raise ValueError(f"Could not find source image for generation_id={source_generation_id}")

        source_image_unique_id = result.data["result_image_unique_id"]
        source_image_url = image_cache.get_cached_image_proxy_url(source_image_unique_id)

        quality_level = self.gen_data.get("quality_level", 2)
        tier_config = settings.image_edit.tiers.get(quality_level)
        if not tier_config:
            raise ValueError(f"Tier configuration for image_edit level {quality_level} not found.")

        final_prompt = PROMPT_IMAGE_EDIT_DEFAULT.replace("{{USER_PROMPT}}", user_prompt)

        request_payload = {
            "model": tier_config.model,
            "image_urls": [source_image_url],
            "generation_type": GenerationType.IMAGE_EDIT.value,
            "prompt": final_prompt,
            "temperature": 0.5,
            "aspect_ratio": '9:16',
        }

        metadata = {
            "processed_uids": [source_image_unique_id],
        }

        return PipelineOutput(request_payload=request_payload, caption=None, metadata=metadata)
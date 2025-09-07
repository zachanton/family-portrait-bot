# aiogram_bot_template/services/pipelines/group_photo.py
from aiogram.utils.i18n import gettext as _
import random

from .base import BasePipeline, PipelineOutput
from aiogram_bot_template.data.constants import ImageRole
from aiogram_bot_template.services import image_cache
from aiogram_bot_template.data.settings import settings
from aiogram_bot_template.services.prompting.factory import get_prompt_strategy

class GroupPhotoPipeline(BasePipeline):
    
    async def prepare_data(self) -> PipelineOutput:
        await self.update_status_func("Preparing your group portrait... 👨‍👩‍👧")
        
        source_images_map = {img["role"]: img for img in self.gen_data.get("source_images", [])}
        photo1_uid = source_images_map.get(ImageRole.PHOTO_1, {}).get("file_unique_id")
        photo2_uid = source_images_map.get(ImageRole.PHOTO_2, {}).get("file_unique_id")

        if not photo1_uid or not photo2_uid:
            raise ValueError("Missing one or both source images for group photo.")

        image_urls = [
            image_cache.get_cached_image_proxy_url(photo1_uid),
            image_cache.get_cached_image_proxy_url(photo2_uid),
        ]

        quality_level = self.gen_data.get("quality_level", 1)
        tier_config = settings.group_photo.tiers.get(quality_level)
        if not tier_config:
            raise ValueError(f"Tier configuration for quality level {quality_level} not found.")

        strategy = get_prompt_strategy(tier_config.client)
        prompt_payload = strategy.create_group_photo_payload()

        is_retry = self.gen_data.get("is_retry", False)
        seed_to_use = random.randint(0, 2**32 - 1) if is_retry else 42

        request_payload = {
            "model": tier_config.model,
            "image_urls": image_urls,
            "seed": seed_to_use,
            **prompt_payload,
        }

        caption = _("✨ Here is your beautiful group portrait!")

        return PipelineOutput(
            request_payload=request_payload,
            caption=caption,
            metadata={}
        )
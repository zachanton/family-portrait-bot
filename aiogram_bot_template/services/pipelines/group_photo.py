# aiogram_bot_template/services/pipelines/group_photo.py
import random
from aiogram.utils.i18n import gettext as _
from aiogram_bot_template.services import image_cache
from aiogram_bot_template.data.settings import settings
from aiogram_bot_template.services.prompting.factory import get_prompt_strategy
from .base import BasePipeline, PipelineOutput

class GroupPhotoPipeline(BasePipeline):
    async def prepare_data(self) -> PipelineOutput:
        await self.update_status_func("Preparing your group portrait... 👨‍👩‍👧")

        photos_collected = self.gen_data.get("photos_collected", [])
        if len(photos_collected) < 2:
            raise ValueError("Missing one or both source images for group photo.")

        photo1_processed_files = photos_collected[0].get("processed_files", {})
        photo2_processed_files = photos_collected[1].get("processed_files", {})

        photo1_uid = photo1_processed_files.get("half_body")
        photo2_uid = photo2_processed_files.get("half_body")

        if not photo1_uid or not photo2_uid:
            raise ValueError("Missing processed file unique ID for one or both images.")

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
        return PipelineOutput(request_payload=request_payload, caption=caption, metadata={})
# aiogram_bot_template/services/pipelines/group_photo.py
import uuid
from aiogram.utils.i18n import gettext as _
from aiogram_bot_template.services import image_cache
from aiogram_bot_template.data.settings import settings
from aiogram_bot_template.services.prompting.factory import get_prompt_strategy
from aiogram_bot_template.services import photo_processing
from .base import BasePipeline, PipelineOutput

class GroupPhotoPipeline(BasePipeline):
    
    async def prepare_data(self) -> PipelineOutput:
        """
        Prepares two composite images from two source photos:
        1. A full composite for the main generation.
        2. A faces-only composite for potential future use.
        """
        await self.update_status_func("Preparing your group portrait... 👨‍👩‍👧")

        photos_collected = self.gen_data.get("photos_collected", [])
        if len(photos_collected) < 2:
            raise ValueError("Missing one or both source images for group photo.")

        photo1_uid = photos_collected[0].get("file_unique_id")
        photo2_uid = photos_collected[1].get("file_unique_id")

        if not photo1_uid or not photo2_uid:
            raise ValueError("Missing original file unique ID for one or both images.")

        photo1_bytes, content_type = await image_cache.get_cached_image_bytes(photo1_uid, self.cache_pool)
        photo2_bytes, content_type = await image_cache.get_cached_image_bytes(photo2_uid, self.cache_pool)

        if not photo1_bytes or not photo2_bytes:
            raise ValueError("Could not retrieve original image bytes from cache.")

        await self.update_status_func("Creating a composite draft... 🖼️")
        
        composite_bytes, faces_only_bytes = photo_processing.create_composite_image(photo1_bytes, photo2_bytes)
        if not composite_bytes or not faces_only_bytes:
            raise RuntimeError("Failed to create a composite image draft.")

        request_id_str = self.gen_data.get('request_id', uuid.uuid4().hex)
        composite_uid = f"composite_{request_id_str}"
        await image_cache.cache_image_bytes(composite_uid, composite_bytes, "image/jpeg", self.cache_pool)
        
        faces_only_uid = f"faces_only_{request_id_str}"
        await image_cache.cache_image_bytes(faces_only_uid, faces_only_bytes, "image/jpeg", self.cache_pool)
        
        self.log.info("Cached composite and faces-only images", composite_uid=composite_uid, faces_only_uid=faces_only_uid)
        
        image_urls = [image_cache.get_cached_image_proxy_url(composite_uid)]

        quality_level = self.gen_data.get("quality_level", 1)
        tier_config = settings.group_photo.tiers.get(quality_level)
        if not tier_config:
            raise ValueError(f"Tier configuration for quality level {quality_level} not found.")

        strategy = get_prompt_strategy(tier_config.client)
        prompt_payload = strategy.create_group_photo_payload(style=None) 

        request_payload = {
            "model": tier_config.model,
            "image_urls": image_urls,
            **prompt_payload,
        }
        
        caption = _("✨ Here is your beautiful group portrait!")
        metadata = { 
            "composite_uid": composite_uid,
            "faces_only_uid": faces_only_uid,
        }
        
        return PipelineOutput(request_payload=request_payload, caption=caption, metadata=metadata)
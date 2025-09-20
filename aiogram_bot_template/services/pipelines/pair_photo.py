# aiogram_bot_template/services/pipelines/pair_photo.py
import uuid
from aiogram.utils.i18n import gettext as _
from aiogram_bot_template.services import image_cache, photo_processing, enhancers
from aiogram_bot_template.data.settings import settings
from aiogram_bot_template.services.prompting.factory import get_prompt_strategy
from aiogram_bot_template.data.constants import GenerationType, ImageRole
from .base import BasePipeline, PipelineOutput

class PairPhotoPipeline(BasePipeline):
    
    async def prepare_data(self) -> PipelineOutput:
        """
        Prepares two composite images from two source photos for a pair portrait.
        """
        await self.update_status_func("Preparing your pair portrait... 👨‍👩‍👧")

        photos_collected = self.gen_data.get("photos_collected", [])
        if len(photos_collected) < 2:
            raise ValueError("Missing one or both source images for pair photo.")

        father_photo = next((p for p in photos_collected if p.get("role") == ImageRole.FATHER.value), photos_collected)
        mother_photo = next((p for p in photos_collected if p.get("role") == ImageRole.MOTHER.value), photos_collected)

        father_uid = father_photo.get("file_unique_id")
        mother_uid = mother_photo.get("file_unique_id")

        if not father_uid or not mother_uid:
            raise ValueError("Missing original file unique ID for one or both images.")

        father_bytes, _ = await image_cache.get_cached_image_bytes(father_uid, self.cache_pool)
        mother_bytes, _ = await image_cache.get_cached_image_bytes(mother_uid, self.cache_pool)

        if not father_bytes or not mother_bytes:
            raise ValueError("Could not retrieve original image bytes from cache.")

        await self.update_status_func("Creating a composite draft... 🖼️")
        
        composite_bytes, _, _, _ = photo_processing.create_composite_image(father_bytes, mother_bytes)
        
        if not composite_bytes:
            raise RuntimeError("Failed to create a composite image draft.")

        request_id_str = self.gen_data.get('request_id', uuid.uuid4().hex)
        composite_uid = f"composite_pair_{request_id_str}"
        await image_cache.cache_image_bytes(composite_uid, composite_bytes, "image/jpeg", self.cache_pool)
        
        composite_url = image_cache.get_cached_image_proxy_url(composite_uid)
        
        await self.update_status_func("Analyzing facial features for accuracy... 🧐")
        identity_lock_data = await enhancers.get_identity_lock_data(composite_url)
        
        if not identity_lock_data:
            self.log.warning("Failed to get identity lock data, proceeding with a placeholder.")
            identity_lock_text = '"Identity analysis failed, using fallback."'
        else:
            identity_lock_text = f"IDENTITY_LOCK_DATA:\n```json\n{identity_lock_data}\n```"

        quality_level = self.gen_data.get("quality_level", 1)
        tier_config = settings.group_photo.tiers.get(quality_level)
        strategy = get_prompt_strategy(tier_config.client)
        
        prompt_payload = strategy.create_pair_photo_payload(style=self.gen_data.get("style"))
        
        prompt_payload["prompt"] = prompt_payload["prompt"].replace(
            "{{IDENTITY_LOCK_DATA}}", identity_lock_text
        )

        request_payload = {
            "model": tier_config.model,
            "image_urls": [composite_url],
            "generation_type": GenerationType.PAIR_PHOTO.value,
            **prompt_payload,
        }
        
        caption = _("✨ Here is your beautiful portrait!")
        metadata = { "composite_uid": composite_uid }
        
        return PipelineOutput(request_payload=request_payload, caption=caption, metadata=metadata)
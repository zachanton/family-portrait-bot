# aiogram_bot_template/services/pipelines/group_photo.py
import uuid
from aiogram.utils.i18n import gettext as _
from aiogram_bot_template.services import image_cache
from aiogram_bot_template.data.settings import settings
from aiogram_bot_template.services.prompting.factory import get_prompt_strategy
from aiogram_bot_template.services import image_cache, photo_processing, prompt_enhancer
# --- NEW: Import GenerationType ---
from aiogram_bot_template.data.constants import GenerationType
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
        
        # --- MODIFIED: Unpack all four return values ---
        composite_bytes, faces_only_bytes, _, _ = photo_processing.create_composite_image(photo1_bytes, photo2_bytes)
        if not composite_bytes or not faces_only_bytes:
            raise RuntimeError("Failed to create a composite image draft.")

        request_id_str = self.gen_data.get('request_id', uuid.uuid4().hex)
        composite_uid = f"composite_{request_id_str}"
        await image_cache.cache_image_bytes(composite_uid, composite_bytes, "image/jpeg", self.cache_pool)
        
        faces_only_uid = f"faces_only_{request_id_str}"
        await image_cache.cache_image_bytes(faces_only_uid, faces_only_bytes, "image/jpeg", self.cache_pool)
        
        self.log.info("Cached composite and faces-only images", composite_uid=composite_uid, faces_only_uid=faces_only_uid)
        
        composite_url = image_cache.get_cached_image_proxy_url(composite_uid)
        
        await self.update_status_func("Analyzing facial features for accuracy... 🧐")
        identity_lock_data = await prompt_enhancer.get_identity_lock_data(composite_url)
        
        if not identity_lock_data:
            self.log.warning("Failed to get identity lock data, proceeding with a placeholder.")
            identity_lock_text = '"Identity analysis failed, using fallback."'
        else:
            identity_lock_text = f"IDENTITY_LOCK_DATA:\n```json\n{identity_lock_data}\n```"

        quality_level = self.gen_data.get("quality_level", 1)
        tier_config = settings.group_photo.tiers.get(quality_level)
        strategy = get_prompt_strategy(tier_config.client)
        prompt_payload = strategy.create_group_photo_payload(style=self.gen_data.get("style"))
        
        prompt_payload["prompt"] = prompt_payload["prompt"].replace(
            "{{IDENTITY_LOCK_DATA}}", identity_lock_text
        )

        # --- NEW: Add generation_type to payload for client context ---
        request_payload = {
            "model": tier_config.model,
            "image_urls": [composite_url],
            "generation_type": GenerationType.GROUP_PHOTO.value,
            **prompt_payload,
        }
        
        caption = _("✨ Here is your beautiful group portrait!")
        metadata = { "composite_uid": composite_uid }
        
        return PipelineOutput(request_payload=request_payload, caption=caption, metadata=metadata)
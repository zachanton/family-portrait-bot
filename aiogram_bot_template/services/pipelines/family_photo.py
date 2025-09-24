# aiogram_bot_template/services/pipelines/family_photo.py
import asyncio
import uuid
from aiogram.utils.i18n import gettext as _
from aiogram_bot_template.services import image_cache, photo_processing
from aiogram_bot_template.services.enhancers import style_enhancer
from aiogram_bot_template.data.settings import settings
from aiogram_bot_template.services.prompting.factory import get_prompt_strategy
from aiogram_bot_template.data.constants import GenerationType, ImageRole
from .base import BasePipeline, PipelineOutput
from aiogram.types import BufferedInputFile

class FamilyPhotoPipeline(BasePipeline):
    
    async def prepare_data(self) -> PipelineOutput:
        """
        Prepares a single composite image for the family photo generation.
        This composite is created from the parents' visual representations and the
        selected child's image, then sent for debug and to the AI model.
        """
        await self.update_status_func("Preparing your family portrait... 👨‍👩‍👧")
        
        photos_collected = self.gen_data.get("photos_collected", [])
        if len(photos_collected) < 3:
            raise ValueError(f"Missing one or more source images for the family photo. Expected 3, got {len(photos_collected)}")

        father_visual_photo = next((p for p in photos_collected if p.get("role") == ImageRole.FATHER_VISUAL.value), None)
        mother_visual_photo = next((p for p in photos_collected if p.get("role") == ImageRole.MOTHER_VISUAL.value), None)
        child_photo = next((p for p in photos_collected if p.get("role") == ImageRole.CHILD.value), None)

        if not all([father_visual_photo, mother_visual_photo, child_photo]):
            raise ValueError("Could not identify all roles (father_visual, mother_visual, child) in source images.")

        async def get_bytes(photo_info):
            bytes_tuple = await image_cache.get_cached_image_bytes(photo_info['file_unique_id'], self.cache_pool)
            return bytes_tuple[0]

        father_visual_bytes, mother_visual_bytes, child_bytes = await asyncio.gather(
            get_bytes(father_visual_photo),
            get_bytes(mother_visual_photo),
            get_bytes(child_photo)
        )

        if not all([father_visual_bytes, mother_visual_bytes, child_bytes]):
            raise ValueError("Could not retrieve all necessary image bytes from cache.")

        await self.update_status_func("Creating family composite for the AI... 🖼️")
        

        composite_bytes = photo_processing.create_vertical_collage(
            image_bytes_list=[ mother_visual_bytes, child_bytes, father_visual_bytes ],
        )
        
        
        if not composite_bytes:
            raise RuntimeError("Failed to create the family composite image for the model.")
        
        request_id_str = self.gen_data.get('request_id', uuid.uuid4().hex)
        composite_uid = f"composite_family_for_model_{request_id_str}"
        await image_cache.cache_image_bytes(composite_uid, composite_bytes, "image/jpeg", self.cache_pool)

        composite_url = image_cache.get_cached_image_proxy_url(composite_uid)

        quality_level = self.gen_data.get("quality_level", 1)
        generation_type = self.gen_data.get("type", GenerationType.FAMILY_PHOTO.value)
        generation_config = getattr(settings, generation_type)
        tier_config = generation_config.tiers.get(quality_level)
        
        if not tier_config:
             raise ValueError(f"Tier configuration for {generation_type} level {quality_level} not found.")

        await self.update_status_func("Designing your photoshoot... 🎨")
        generation_count = tier_config.count
        
        # Note: The photoshoot plan now receives the composite URL as its reference
        photoshoot_plan = await style_enhancer.get_style_data(composite_url, num_shots=generation_count)
        
        strategy = get_prompt_strategy(tier_config.client)
        prompt_payload = strategy.create_family_photo_payload(style=self.gen_data.get("style"))

        request_payload = {
            "model": tier_config.model,
            "image_urls": [composite_url],
            "generation_type": GenerationType.FAMILY_PHOTO.value,
            **prompt_payload,
        }
        
        caption = None
        
        metadata = { 
            "composite_uid": composite_uid,
            "photoshoot_plan": photoshoot_plan.shots if photoshoot_plan else None
        }

        return PipelineOutput(request_payload=request_payload, caption=caption, metadata=metadata)
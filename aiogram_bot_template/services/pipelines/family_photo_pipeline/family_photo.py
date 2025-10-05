# aiogram_bot_template/services/pipelines/family_photo.py
import asyncio
import uuid
from aiogram.utils.i18n import gettext as _
from aiogram_bot_template.services import image_cache, photo_processing
from aiogram_bot_template.services.enhancers import family_prompt_enhancer
from aiogram_bot_template.data.settings import settings
from aiogram_bot_template.data.constants import GenerationType, ImageRole
from ..base import BasePipeline, PipelineOutput

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
            raise ValueError(f"Missing source images for the family photo. Expected 3, got {len(photos_collected)}")
        
        father_horizontal_photo = next((p for p in photos_collected if p.get("role") == ImageRole.FATHER_HORIZONTAL.value), None)
        mother_horizontal_photo = next((p for p in photos_collected if p.get("role") == ImageRole.MOTHER_HORIZONTAL.value), None)
        child_photo = next((p for p in photos_collected if p.get("role") == ImageRole.CHILD.value), None)

        if not all([father_horizontal_photo, mother_horizontal_photo, child_photo]):
            raise ValueError("Could not identify all roles (father/mother front/side, child) in source images.")

        async def get_bytes(photo_info):
            if not photo_info or not photo_info.get('file_unique_id'):
                return None
            bytes_tuple = await image_cache.get_cached_image_bytes(photo_info['file_unique_id'], self.cache_pool)
            return bytes_tuple[0]

        mother_horizontal_bytes, father_horizontal_bytes, child_bytes = await asyncio.gather(
            get_bytes(mother_horizontal_photo),
            get_bytes(father_horizontal_photo),
            get_bytes(child_photo)
        )

        if not all([mother_horizontal_bytes, father_horizontal_bytes, child_bytes]):
            raise ValueError("Could not retrieve all necessary image bytes from cache.")

        await self.update_status_func("Creating family composite for the AI... 🖼️")

        request_id_str = self.gen_data.get('request_id', uuid.uuid4().hex)
        
        # This composite is the main input for the prompt enhancer and the generation model
        vertical_stack_bytes = photo_processing.stack_three_images(mother_horizontal_bytes, child_bytes, father_horizontal_bytes)
        vertical_stack_uid = f"vertical_stack_{request_id_str}"
        await image_cache.cache_image_bytes(vertical_stack_uid, vertical_stack_bytes, "image/jpeg", self.cache_pool)
        vertical_stack_url = image_cache.get_cached_image_proxy_url(vertical_stack_uid)

        quality_level = self.gen_data.get("quality_level", 1)
        generation_type = self.gen_data.get("type", GenerationType.FAMILY_PHOTO.value)
        generation_config = getattr(settings, generation_type)
        tier_config = generation_config.tiers.get(quality_level)
        
        if not tier_config:
             raise ValueError(f"Tier configuration for {generation_type} level {quality_level} not found.")

        await self.update_status_func("Designing your photoshoot... 🎨")
        
        # A single call gets us the list of final, ready-to-use prompts
        completed_prompts = await family_prompt_enhancer.get_enhanced_family_prompts(
            composite_image_url=vertical_stack_url,
            num_prompts=tier_config.count
        )
        if not completed_prompts:
            self.log.error("Family prompt enhancer failed. Cannot proceed with generation.")
            raise RuntimeError("Failed to generate family photo prompts.")

        request_payload = {
            "model": tier_config.model,
            "image_urls": [vertical_stack_url],
            "generation_type": GenerationType.FAMILY_PHOTO.value,
            "prompt": completed_prompts[0], # Use the first prompt as a representative base
            "temperature": 0.5
        }
        
        caption = None
        
        metadata = { 
            "processed_uids": [vertical_stack_uid],
            "completed_prompts": completed_prompts # Pass the full list to the worker
        }

        return PipelineOutput(request_payload=request_payload, caption=caption, metadata=metadata)
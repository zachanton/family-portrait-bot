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
        if len(photos_collected) < 5: # Expecting mom front/side, dad front/side, child
            raise ValueError(f"Missing one or more source images for the family photo. Expected 5, got {len(photos_collected)}")

        father_front_photo = next((p for p in photos_collected if p.get("role") == ImageRole.FATHER_FRONT.value), None)
        mother_front_photo = next((p for p in photos_collected if p.get("role") == ImageRole.MOTHER_FRONT.value), None)
        father_horizontal_photo = next((p for p in photos_collected if p.get("role") == ImageRole.FATHER_HORIZONTAL.value), None)
        mother_horizontal_photo = next((p for p in photos_collected if p.get("role") == ImageRole.MOTHER_HORIZONTAL.value), None)
        child_photo = next((p for p in photos_collected if p.get("role") == ImageRole.CHILD.value), None)

        if not all([father_front_photo, mother_front_photo, father_horizontal_photo, mother_horizontal_photo, child_photo]):
            raise ValueError("Could not identify all roles (father/mother front/side, child) in source images.")

        async def get_bytes(photo_info):
            if not photo_info or not photo_info.get('file_unique_id'):
                return None
            bytes_tuple = await image_cache.get_cached_image_bytes(photo_info['file_unique_id'], self.cache_pool)
            return bytes_tuple[0]

        mother_front_bytes, mother_horizontal_bytes, father_front_bytes, father_horizontal_bytes, child_bytes = await asyncio.gather(
            get_bytes(mother_front_photo),
            get_bytes(mother_horizontal_photo),
            get_bytes(father_front_photo),
            get_bytes(father_horizontal_photo),
            get_bytes(child_photo)
        )

        if not all([mother_front_bytes, mother_horizontal_bytes, father_front_bytes, father_horizontal_bytes, child_bytes]):
            raise ValueError("Could not retrieve all necessary image bytes from cache.")

        await self.update_status_func("Creating family composite for the AI... 🖼️")

        request_id_str = self.gen_data.get('request_id', uuid.uuid4().hex)
        mother_horizontal_uid = f"mother_horizontal_{request_id_str}"
        await image_cache.cache_image_bytes(mother_horizontal_uid, mother_horizontal_bytes, "image/jpeg", self.cache_pool)
        mother_horizontal_url = image_cache.get_cached_image_proxy_url(mother_horizontal_uid)

        father_horizontal_uid = f"father_horizontal_{request_id_str}"
        await image_cache.cache_image_bytes(father_horizontal_uid, father_horizontal_bytes, "image/jpeg", self.cache_pool)
        father_horizontal_url = image_cache.get_cached_image_proxy_url(father_horizontal_uid)

        child_uid = f"child_{request_id_str}"
        await image_cache.cache_image_bytes(child_uid, child_bytes, "image/jpeg", self.cache_pool)
        child_url = image_cache.get_cached_image_proxy_url(child_uid)


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
        generation_count = tier_config.count
        # photoshoot_plan = await style_enhancer.get_style_data(main_composite_url, num_shots=generation_count)
        photoshoot_plan = None

        strategy = get_prompt_strategy(tier_config.client)
        prompt_payload = strategy.create_family_photo_payload(style=self.gen_data.get("style"))

        request_payload = {
            "model": tier_config.model,
            "image_urls": [ vertical_stack_url ],
            "generation_type": GenerationType.FAMILY_PHOTO.value,
            **prompt_payload,
        }
        
        caption = None
        
        metadata = { 
            "processed_uids": [ vertical_stack_uid ],
            "photoshoot_plan": photoshoot_plan.shots if photoshoot_plan else None
        }

        return PipelineOutput(request_payload=request_payload, caption=caption, metadata=metadata)
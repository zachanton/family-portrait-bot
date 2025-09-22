# aiogram_bot_template/services/pipelines/family_photo.py
import uuid
from aiogram.utils.i18n import gettext as _
from aiogram_bot_template.services import image_cache, photo_processing
from aiogram_bot_template.services.enhancers import style_enhancer
from aiogram_bot_template.data.settings import settings
from aiogram_bot_template.services.prompting.factory import get_prompt_strategy
from aiogram_bot_template.data.constants import GenerationType, ImageRole
from .base import BasePipeline, PipelineOutput

class FamilyPhotoPipeline(BasePipeline):
    
    async def prepare_data(self) -> PipelineOutput:
        """
        Prepares a composite image and fetches a complete photoshoot plan (N poses/wardrobes)
        to be used by the generation worker.
        """
        await self.update_status_func("Preparing your family portrait... 👨‍👩‍👧")
        
        photos_collected = self.gen_data.get("photos_collected", [])
        if len(photos_collected) < 3:
            raise ValueError("Missing one or more source images for the family photo.")

        father_photo = next((p for p in photos_collected if p.get("role") == ImageRole.FATHER.value), None)
        mother_photo = next((p for p in photos_collected if p.get("role") == ImageRole.MOTHER.value), None)
        child_photo = next((p for p in photos_collected if p.get("role") == ImageRole.CHILD.value), None)

        if not all([father_photo, mother_photo, child_photo]):
            raise ValueError("Could not identify all roles (father, mother, child) in source images.")

        father_bytes, content_type = await image_cache.get_cached_image_bytes(father_photo['file_unique_id'], self.cache_pool)
        mother_bytes, content_type = await image_cache.get_cached_image_bytes(mother_photo['file_unique_id'], self.cache_pool)
        child_bytes, content_type = await image_cache.get_cached_image_bytes(child_photo['file_unique_id'], self.cache_pool)

        if not all([father_bytes, mother_bytes, child_bytes]):
            raise ValueError("Could not retrieve all three image bytes from cache.")

        await self.update_status_func("Creating a family composite draft... 🖼️")
        
        composite_bytes, mom_bytes, dad_bytes, child_bytes = photo_processing.create_composite_image(mother_bytes, father_bytes, child_bytes)
        
        if not composite_bytes:
            raise RuntimeError("Failed to create a family composite image draft.")

        request_id_str = self.gen_data.get('request_id', uuid.uuid4().hex)
        
        composite_uid = f"composite_family_{request_id_str}"
        await image_cache.cache_image_bytes(composite_uid, composite_bytes, "image/jpeg", self.cache_pool)
        composite_url = image_cache.get_cached_image_proxy_url(composite_uid)
        
        # Other images are cached for potential debug, not used in payload
        mom_uid = f"mom_{request_id_str}"
        await image_cache.cache_image_bytes(mom_uid, mom_bytes, "image/jpeg", self.cache_pool)
        dad_uid = f"dad_{request_id_str}"
        await image_cache.cache_image_bytes(dad_uid, dad_bytes, "image/jpeg", self.cache_pool)
        child_uid = f"child_{request_id_str}"
        await image_cache.cache_image_bytes(child_uid, child_bytes, "image/jpeg", self.cache_pool)

        image_urls = [ composite_url ]

        quality_level = self.gen_data.get("quality_level", 1)
        generation_type = self.gen_data.get("type", GenerationType.FAMILY_PHOTO.value)
        generation_config = getattr(settings, generation_type)
        tier_config = generation_config.tiers.get(quality_level)
        
        if not tier_config:
             raise ValueError(f"Tier configuration for {generation_type} level {quality_level} not found.")

        await self.update_status_func("Designing your photoshoot... 🎨")
        generation_count = tier_config.count
        photoshoot_plan = await style_enhancer.get_style_data(composite_url, num_shots=generation_count)
        
        strategy = get_prompt_strategy(tier_config.client)
        prompt_payload = strategy.create_family_photo_payload(style=self.gen_data.get("style"))

        request_payload = {
            "model": tier_config.model,
            "image_urls": image_urls,
            "generation_type": GenerationType.FAMILY_PHOTO.value,
            **prompt_payload,
        }
        
        caption = None
        
        metadata = { 
            "composite_uid": composite_uid,
            "mom_uid": mom_uid,
            "dad_uid": dad_uid,
            "child_uid": child_uid,
            # Store the entire plan for the worker to use
            "photoshoot_plan": photoshoot_plan.shots if photoshoot_plan else None
        }
        
        return PipelineOutput(request_payload=request_payload, caption=caption, metadata=metadata)
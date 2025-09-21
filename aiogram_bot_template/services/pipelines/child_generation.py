# aiogram_bot_template/services/pipelines/child_generation.py
import uuid
from aiogram.utils.i18n import gettext as _
from aiogram_bot_template.services import image_cache, photo_processing
from aiogram_bot_template.data.settings import settings
from aiogram_bot_template.services.prompting.factory import get_prompt_strategy
from aiogram_bot_template.data.constants import ChildResemblance, GenerationType, ImageRole
from .base import BasePipeline, PipelineOutput

class ChildGenerationPipeline(BasePipeline):
    
    async def prepare_data(self) -> PipelineOutput:
        await self.update_status_func(_("Analyzing parental features... 🧬"))

        photos_collected = self.gen_data.get("photos_collected", [])
        if len(photos_collected) < 2:
            raise ValueError("Missing one or both source images for child generation.")

        # Find photos by their assigned role for robustness
        mom_photo = next((p for p in photos_collected if p.get("role") == ImageRole.MOTHER.value), None)
        dad_photo = next((p for p in photos_collected if p.get("role") == ImageRole.FATHER.value), None)

        if not mom_photo or not dad_photo:
            raise ValueError("Could not identify Mom or Dad's photo from the collected images.")

        mom_uid = mom_photo.get("file_unique_id")
        dad_uid = dad_photo.get("file_unique_id")
        
        if not mom_uid or not dad_uid:
            raise ValueError("Missing file unique ID for one or both parent images.")

        mom_bytes, content_type = await image_cache.get_cached_image_bytes(mom_uid, self.cache_pool)
        dad_bytes, content_type = await image_cache.get_cached_image_bytes(dad_uid, self.cache_pool)
        if not mom_bytes or not dad_bytes:
            raise ValueError("Could not retrieve original image bytes from cache.")

        # The order for composite creation (mom, then dad) can be consistent now
        composite_bytes, mom_bytes, dad_bytes, child_bytes = photo_processing.create_composite_image(mom_bytes, dad_bytes)
        if not composite_bytes:
            raise RuntimeError("Failed to create a composite image of parents.")

        request_id_str = self.gen_data.get('request_id', uuid.uuid4().hex)

        composite_uid = f"composite_child_{request_id_str}"
        await image_cache.cache_image_bytes(composite_uid, composite_bytes, "image/jpeg", self.cache_pool)
        
        mom_uid_cache = f"mom_{request_id_str}"
        await image_cache.cache_image_bytes(mom_uid_cache, mom_bytes, "image/jpeg", self.cache_pool)
        mom_url = image_cache.get_cached_image_proxy_url(mom_uid_cache)

        dad_uid_cache = f"dad_{request_id_str}"
        await image_cache.cache_image_bytes(dad_uid_cache, dad_bytes, "image/jpeg", self.cache_pool)
        dad_url = image_cache.get_cached_image_proxy_url(dad_uid_cache)
        
        quality_level = self.gen_data.get("quality_level", 1)
        tier_config = settings.child_generation.tiers.get(quality_level)
        if not tier_config:
            raise ValueError(f"Tier configuration for child_generation level {quality_level} not found.")

        strategy = get_prompt_strategy(tier_config.client)
        
        prompt_payload = strategy.create_child_generation_payload(
            child_gender=self.gen_data["child_gender"],
            child_age=self.gen_data["child_age"],
            child_resemblance=self.gen_data["child_resemblance"],
        )

        prompt = prompt_payload["prompt"]
        prompt = prompt.replace("{{child_age}}", self.gen_data["child_age"])
        prompt = prompt.replace("{{child_gender}}", self.gen_data["child_gender"])
        prompt = prompt.replace("{{child_resemblance}}", self.gen_data["child_resemblance"])
        prompt_payload["prompt"] = prompt

        request_payload = { 
            "model": tier_config.model, 
            "image_urls": [mom_url, dad_url], 
            "generation_type": GenerationType.CHILD_GENERATION.value,
            **prompt_payload 
        }
        
        caption = None
        
        metadata = { 
            "composite_uid": composite_uid,
            "mom_uid": mom_uid_cache,
            "dad_uid": dad_uid_cache,
        }
        
        return PipelineOutput(request_payload=request_payload, caption=caption, metadata=metadata)
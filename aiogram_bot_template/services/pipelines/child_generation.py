# aiogram_bot_template/services/pipelines/child_generation.py
import uuid
from aiogram.utils.i18n import gettext as _
from aiogram_bot_template.services import image_cache, photo_processing
# --- MODIFICATION: Import both enhancers ---
from aiogram_bot_template.services.enhancers import eye_enhancer, hairstyle_enhancer
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

        composite_bytes, mom_bytes, dad_bytes, child_bytes = photo_processing.create_composite_image(mom_bytes, dad_bytes)

        request_id_str = self.gen_data.get('request_id', uuid.uuid4().hex)

        composite_uid = f"composite_family_{request_id_str}"
        await image_cache.cache_image_bytes(composite_uid, composite_bytes, "image/jpeg", self.cache_pool)
        mom_uid = f"mom_{request_id_str}"
        await image_cache.cache_image_bytes(mom_uid, mom_bytes, "image/jpeg", self.cache_pool)
        dad_uid = f"dad_{request_id_str}"
        await image_cache.cache_image_bytes(dad_uid, dad_bytes, "image/jpeg", self.cache_pool)

        mom_url = image_cache.get_cached_image_proxy_url(mom_uid)
        dad_url = image_cache.get_cached_image_proxy_url(dad_uid)
        
        quality_level = self.gen_data.get("quality_level", 1)
        tier_config = settings.child_generation.tiers.get(quality_level)
        if not tier_config:
            raise ValueError(f"Tier configuration for child_generation level {quality_level} not found.")

        child_resemblance = self.gen_data["child_resemblance"]
        if child_resemblance == ChildResemblance.MOM.value:
            resemblance_parent_url = mom_url
            non_resemblance_parent_url = dad_url
        else:
            resemblance_parent_url = dad_url
            non_resemblance_parent_url = mom_url
        
        await self.update_status_func(_("Designing child's features... ✨"))
        eye_description_text = await eye_enhancer.get_eye_description(
            non_resemblance_parent_url=non_resemblance_parent_url
        )
        
        # Fallback in case the enhancer fails
        if not eye_description_text:
            self.log.warning("Eye enhancer failed, using fallback description.")
            eye_description_text = "The child has clear, bright eyes that perfectly match the color and pattern of the non-resemblance parent."

        hairstyle_descriptions = await hairstyle_enhancer.get_hairstyle_descriptions(
            num_hairstyles=tier_config.count,
            child_age=self.gen_data["child_age"],
            child_gender=self.gen_data["child_gender"],
        )

        if not hairstyle_descriptions or len(hairstyle_descriptions) < tier_config.count:
            self.log.warning("Hairstyle enhancer failed or returned too few styles, using fallback.", 
                             requested=tier_config.count, returned=len(hairstyle_descriptions or []))
            # Create a simple fallback list
            fallback_style = "a simple, neat hairstyle."
            hairstyle_descriptions = [fallback_style] * tier_config.count


        strategy = get_prompt_strategy(tier_config.client)
        
        prompt_payload = strategy.create_child_generation_payload(
            child_gender=self.gen_data["child_gender"],
            child_age=self.gen_data["child_age"],
            child_resemblance=child_resemblance,
        )
        
        request_payload = { 
            "model": tier_config.model, 
            "image_urls": [resemblance_parent_url], 
            "generation_type": GenerationType.CHILD_GENERATION.value,
            **prompt_payload 
        }
        
        caption = None
        
        metadata = {
            "composite_uid": composite_uid,
            "mom_uid": mom_uid,
            "dad_uid": dad_uid,
            "eye_description_text": eye_description_text,
            "hairstyle_descriptions": hairstyle_descriptions,
        }
        
        return PipelineOutput(request_payload=request_payload, caption=caption, metadata=metadata)
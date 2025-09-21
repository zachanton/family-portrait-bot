# aiogram_bot_template/services/pipelines/child_generation.py
import uuid
from aiogram.utils.i18n import gettext as _
from aiogram_bot_template.services import image_cache, photo_processing
from aiogram_bot_template.data.settings import settings
from aiogram_bot_template.services.prompting.factory import get_prompt_strategy
from aiogram_bot_template.data.constants import ChildResemblance, GenerationType
from .base import BasePipeline, PipelineOutput

class ChildGenerationPipeline(BasePipeline):
    
    async def prepare_data(self) -> PipelineOutput:
        await self.update_status_func(_("Analyzing parental features... 🧬"))

        photos_collected = self.gen_data.get("photos_collected", [])
        if len(photos_collected) < 2:
            raise ValueError("Missing one or both source images for child generation.")

        photo1_uid = photos_collected[0].get("file_unique_id")
        photo2_uid = photos_collected[1].get("file_unique_id")
        if not photo1_uid or not photo2_uid:
            raise ValueError("Missing file unique ID for one or both images.")

        p1_bytes, content_type = await image_cache.get_cached_image_bytes(photo1_uid, self.cache_pool)
        p2_bytes, content_type = await image_cache.get_cached_image_bytes(photo2_uid, self.cache_pool)
        if not p1_bytes or not p2_bytes:
            raise ValueError("Could not retrieve original image bytes from cache.")

        composite_bytes, mom_bytes, dad_bytes, p3_bytes = photo_processing.create_composite_image(p1_bytes, p2_bytes)
        if not composite_bytes:
            raise RuntimeError("Failed to create a composite image of parents.")

        request_id_str = self.gen_data.get('request_id', uuid.uuid4().hex)

        composite_uid = f"composite_child_{request_id_str}"
        await image_cache.cache_image_bytes(composite_uid, composite_bytes, "image/jpeg", self.cache_pool)
        composite_url = image_cache.get_cached_image_proxy_url(composite_uid)

        # Determine which face composite to use based on resemblance
        resemblance = self.gen_data["child_resemblance"]
        # if resemblance == ChildResemblance.BOTH.value:
        #     faces_uid = f"faces_only_{request_id_str}"
        #     faces_bytes = composite_bytes
        # elif resemblance == ChildResemblance.MOM.value:
        #     faces_uid = f"mom_face_{request_id_str}"
        #     faces_bytes = p1_bytes
        # else: # ChildResemblance.DAD
        #     faces_uid = f"dad_face_{request_id_str}"
        #     faces_bytes = p2_bytes
        
        mom_uid = f"mom_{request_id_str}"
        await image_cache.cache_image_bytes(mom_uid, mom_bytes, "image/jpeg", self.cache_pool)
        mom_url = image_cache.get_cached_image_proxy_url(mom_uid)

        dad_uid = f"dad_{request_id_str}"
        await image_cache.cache_image_bytes(dad_uid, dad_bytes, "image/jpeg", self.cache_pool)
        dad_url = image_cache.get_cached_image_proxy_url(dad_uid)
        
        
        quality_level = self.gen_data.get("quality_level", 1)
        tier_config = settings.child_generation.tiers.get(quality_level)
        if not tier_config:
            raise ValueError(f"Tier configuration for child_generation level {quality_level} not found.")

        # The enhancer call has been completely removed.
        
        strategy = get_prompt_strategy(tier_config.client)
        
        # The method call is now simpler, without hints.
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
        
        caption = _("✨ Here is your potential child!")
        # Metadata no longer needs to store hints.
        metadata = { 
            "composite_uid": composite_uid,
            "mom_uid": mom_uid,
            "dad_uid": dad_uid,
        }
        
        return PipelineOutput(request_payload=request_payload, caption=caption, metadata=metadata)
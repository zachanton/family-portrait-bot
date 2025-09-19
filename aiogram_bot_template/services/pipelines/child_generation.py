# aiogram_bot_template/services/pipelines/child_generation.py
import uuid
from aiogram.utils.i18n import gettext as _
from aiogram_bot_template.services import image_cache, photo_processing, child_description_generator
from aiogram_bot_template.data.settings import settings
from aiogram_bot_template.services.prompting.factory import get_prompt_strategy
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

        p1_bytes, content_type1 = await image_cache.get_cached_image_bytes(photo1_uid, self.cache_pool)
        p2_bytes, content_type2 = await image_cache.get_cached_image_bytes(photo2_uid, self.cache_pool)
        if not p1_bytes or not p2_bytes:
            raise ValueError("Could not retrieve original image bytes from cache.")

        composite_bytes, faces_only_bytes = photo_processing.create_composite_image(p1_bytes, p2_bytes)
        if not composite_bytes:
            raise RuntimeError("Failed to create a composite image of parents.")

        request_id_str = self.gen_data.get('request_id', uuid.uuid4().hex)

        composite_uid = f"composite_child_{request_id_str}"
        await image_cache.cache_image_bytes(composite_uid, composite_bytes, "image/jpeg", self.cache_pool)
        composite_url = image_cache.get_cached_image_proxy_url(composite_uid)

        faces_only_uid = f"faces_only__{request_id_str}"
        await image_cache.cache_image_bytes(faces_only_uid, faces_only_bytes, "image/jpeg", self.cache_pool)
        faces_only_url = image_cache.get_cached_image_proxy_url(faces_only_uid)
        
        quality_level = self.gen_data.get("quality_level", 1)
        tier_config = settings.child_generation.tiers.get(quality_level)
        if not tier_config:
            raise ValueError(f"Tier configuration for child_generation level {quality_level} not found.")
        generation_count = tier_config.count

        await self.update_status_func(_("Creating a genetic profile for the child... ✍️"))
        
        child_descriptions = await child_description_generator.get_child_descriptions(
            image_url=composite_url,
            child_gender=self.gen_data["child_gender"],
            child_age=self.gen_data["child_age"],
            child_resemblance=self.gen_data["child_resemblance"],
            child_count=generation_count
        )

        if not child_descriptions or len(child_descriptions) < generation_count:
            self.log.error("Failed to generate a sufficient number of child descriptions.",
                           expected=generation_count, got=len(child_descriptions) if child_descriptions else 0)
            raise RuntimeError("Could not generate the necessary creative descriptions for the child.")

        self.log.info("Generated child descriptions", child_count=len(child_descriptions))

        self.log.info(
            "Received child descriptions from generator", 
            descriptions=child_descriptions
        )

        strategy = get_prompt_strategy(tier_config.client)
        prompt_payload = strategy.create_child_generation_payload(
            description=child_descriptions[0],
            child_gender=self.gen_data["child_gender"],
            child_age=self.gen_data["child_age"],
            child_resemblance=self.gen_data["child_resemblance"],
        )

        request_payload = { "model": tier_config.model, "image_urls": [composite_url, faces_only_url], **prompt_payload }
        
        caption = _("✨ Here is your potential child!")
        metadata = { 
            "composite_uid": composite_uid,
            "faces_only_uid": faces_only_uid,
            "child_descriptions": child_descriptions
        }
        
        return PipelineOutput(request_payload=request_payload, caption=caption, metadata=metadata)
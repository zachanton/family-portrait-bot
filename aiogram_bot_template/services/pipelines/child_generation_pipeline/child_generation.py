# aiogram_bot_template/services/pipelines/child_generation.py
import asyncio
import uuid
import numpy as np
from aiogram.utils.i18n import gettext as _
from aiogram_bot_template.services import image_cache, photo_processing, similarity_scorer
from aiogram_bot_template.services.enhancers import (
    parent_visual_enhancer,
    child_prompt_enhancer,
)
from aiogram_bot_template.data.settings import settings
from aiogram_bot_template.data.constants import (
    ChildResemblance,
    GenerationType,
    ImageRole,
)
from ..base import BasePipeline, PipelineOutput


class ChildGenerationPipeline(BasePipeline):
    async def prepare_data(self) -> PipelineOutput:
        await self.update_status_func(_("Analyzing parental features... 🧬"))

        photos_collected = self.gen_data.get("photos_collected", [])
        if not photos_collected:
            raise ValueError(
                "Missing source images for child generation."
            )

        mom_photos = [
            p for p in photos_collected if p.get("role") == ImageRole.MOTHER.value
        ]
        dad_photos = [
            p for p in photos_collected if p.get("role") == ImageRole.FATHER.value
        ]

        if not mom_photos or not dad_photos:
            raise ValueError(
                "Could not identify Mom or Dad's photos from the collected images."
            )

        async def get_all_processed_bytes(photos):
            tasks = [
                image_cache.get_cached_image_bytes(
                    p["file_unique_id"], self.cache_pool
                )
                for p in photos
            ]
            results = await asyncio.gather(*tasks)
            return [b for b, a in results if b is not None]

        father_bytes_list = await get_all_processed_bytes(dad_photos)
        mother_bytes_list = await get_all_processed_bytes(mom_photos)

        mom_centroid, dad_centroid = await asyncio.gather(
            similarity_scorer.calculate_identity_centroid(mother_bytes_list),
            similarity_scorer.calculate_identity_centroid(father_bytes_list)
        )
        self.log.info(
            "Calculated parent identity centroids.",
            has_mom_centroid=mom_centroid is not None,
            has_dad_centroid=dad_centroid is not None
        )

        await self.update_status_func(_("Preparing parent portraits... 🖼️"))
        
        collage_tasks = [
            asyncio.to_thread(photo_processing.create_portrait_collage_from_bytes, mother_bytes_list[:4]),
            asyncio.to_thread(photo_processing.create_portrait_collage_from_bytes, father_bytes_list[:4]),
        ]
        mom_collage_bytes, dad_collage_bytes = await asyncio.gather(*collage_tasks)

        request_id_str = self.gen_data.get("request_id", uuid.uuid4().hex)
        mom_collage_uid, dad_collage_uid = None, None
        mom_collage_url, dad_collage_url = None, None

        if mom_collage_bytes:
            mom_collage_uid = f"collage_mom_processed_{request_id_str}"
            await image_cache.cache_image_bytes(
                mom_collage_uid, mom_collage_bytes, "image/jpeg", self.cache_pool
            )
            mom_collage_url = image_cache.get_cached_image_proxy_url(mom_collage_uid)

        if dad_collage_bytes:
            dad_collage_uid = f"collage_dad_processed_{request_id_str}"
            await image_cache.cache_image_bytes(
                dad_collage_uid, dad_collage_bytes, "image/jpeg", self.cache_pool
            )
            dad_collage_url = image_cache.get_cached_image_proxy_url(dad_collage_uid)

        if not mom_collage_url or not dad_collage_url:
            raise RuntimeError("Failed to create and cache parent collages.")

        await self.update_status_func(
            _("Creating visual representations of parents... 🧑‍🎨")
        )

        visual_tasks = [
            parent_visual_enhancer.get_parent_visual_representation(
                mom_collage_url, role="mother", identity_centroid=mom_centroid, cache_pool=self.cache_pool
            ),
            parent_visual_enhancer.get_parent_visual_representation(
                dad_collage_url, role="father", identity_centroid=dad_centroid, cache_pool=self.cache_pool
            ),
        ]
        mom_visual_horizontal_bytes, dad_visual_horizontal_bytes = await asyncio.gather(*visual_tasks)

        mom_visual_front_bytes, mom_visual_side_bytes = (
            photo_processing.split_and_stack_image_bytes(mom_visual_horizontal_bytes)
            if mom_visual_horizontal_bytes else (None, None)
        )
        dad_visual_front_bytes, dad_visual_side_bytes = (
            photo_processing.split_and_stack_image_bytes(dad_visual_horizontal_bytes)
            if dad_visual_horizontal_bytes else (None, None)
        )
        
        vertical_stack_bytes = photo_processing.stack_two_images(mom_visual_horizontal_bytes, dad_visual_horizontal_bytes)
        vertical_stack_uid = f"vertical_two_stack_{request_id_str}"
        await image_cache.cache_image_bytes(vertical_stack_uid, vertical_stack_bytes, "image/jpeg", self.cache_pool)
        vertical_stack_url = image_cache.get_cached_image_proxy_url(vertical_stack_uid)

        mom_final_ref_url, dad_final_ref_url = mom_collage_url, dad_collage_url
        mom_visual_front_uid, mom_visual_side_uid = None, None
        dad_visual_front_uid, dad_visual_side_uid = None, None
        
        mom_visual_horizontal_uid, dad_visual_horizontal_uid = None, None

        if mom_visual_front_bytes:
            mom_visual_front_uid = f"visual_mom_front_{request_id_str}"
            await image_cache.cache_image_bytes(
                mom_visual_front_uid, mom_visual_front_bytes, "image/jpeg", self.cache_pool
            )
            mom_final_ref_url = image_cache.get_cached_image_proxy_url(mom_visual_front_uid)
            self.log.info("Using enhanced front visual representation for Mom.")
            
            if mom_visual_horizontal_bytes:
                mom_visual_horizontal_uid = f"visual_mom_horizontal_{request_id_str}"
                await image_cache.cache_image_bytes(
                    mom_visual_horizontal_uid, mom_visual_horizontal_bytes, "image/jpeg", self.cache_pool
                )
        else:
            self.log.warning(
                "Failed to generate Mom's visual representation, falling back to collage."
            )

        if dad_visual_front_bytes:
            dad_visual_front_uid = f"visual_dad_front_{request_id_str}"
            await image_cache.cache_image_bytes(
                dad_visual_front_uid, dad_visual_front_bytes, "image/jpeg", self.cache_pool
            )
            dad_final_ref_url = image_cache.get_cached_image_proxy_url(dad_visual_front_uid)
            self.log.info("Using enhanced front visual representation for Dad.")
            
            if dad_visual_horizontal_bytes:
                dad_visual_horizontal_uid = f"visual_dad_horizontal_{request_id_str}"
                await image_cache.cache_image_bytes(
                    dad_visual_horizontal_uid, dad_visual_horizontal_bytes, "image/jpeg", self.cache_pool
                )
        else:
            self.log.warning(
                "Failed to generate Dad's visual representation, falling back to collage."
            )
        
        child_resemblance = self.gen_data["child_resemblance"]
        if child_resemblance == ChildResemblance.MOM.value:
            resemblance_parent_final_url = mom_final_ref_url
            non_resemblance_parent_final_url = dad_final_ref_url
        else:
            resemblance_parent_final_url = dad_final_ref_url
            non_resemblance_parent_final_url = mom_final_ref_url

        await self.update_status_func(_("Designing child's features... ✨"))

        quality_level = self.gen_data.get("quality_level", 1)
        tier_config = settings.child_generation.tiers.get(quality_level)
        if not tier_config:
            raise ValueError(
                f"Tier configuration for child_generation level {quality_level} not found."
            )

        # A single call to get a list of fully-formed prompts
        completed_prompts = await child_prompt_enhancer.get_enhanced_child_prompts(
            non_resemblance_parent_url=non_resemblance_parent_final_url,
            num_prompts=tier_config.count,
            child_age=self.gen_data["child_age"],
            child_gender=self.gen_data["child_gender"],
            child_resemblance=child_resemblance,
        )

        if not completed_prompts:
            self.log.error("Child prompt enhancer failed. Cannot proceed with generation.")
            raise RuntimeError("Failed to generate child prompts.")

        # The base payload now uses the first completed prompt as a template.
        # The worker will cycle through the `completed_prompts` list.
        request_payload = {
            "model": tier_config.model,
            "image_urls": [vertical_stack_url],
            "generation_type": GenerationType.CHILD_GENERATION.value,
            "prompt": completed_prompts[0], # Base prompt for logging purposes
            "temperature": 0.3,
        }

        caption = None

        metadata = {
            "mom_collage_uid": mom_collage_uid,
            "dad_collage_uid": dad_collage_uid,
            "mom_visual_front_uid": mom_visual_front_uid,
            "mom_visual_horizontal_uid": mom_visual_horizontal_uid,
            "dad_visual_front_uid": dad_visual_front_uid,
            "dad_visual_horizontal_uid": dad_visual_horizontal_uid,
            "vertical_stack_uid": vertical_stack_uid,
            "completed_prompts": completed_prompts,
        }

        return PipelineOutput(
            request_payload=request_payload, caption=caption, metadata=metadata
        )
# aiogram_bot_template/services/pipelines/child_generation.py
import asyncio
import uuid
from aiogram.utils.i18n import gettext as _
from aiogram_bot_template.services import image_cache, photo_processing
from aiogram_bot_template.services.enhancers import (
    eye_enhancer,
    hairstyle_enhancer,
    parent_visual_enhancer,
)
from aiogram_bot_template.data.settings import settings
from aiogram_bot_template.services.prompting.factory import get_prompt_strategy
from aiogram_bot_template.data.constants import (
    ChildResemblance,
    GenerationType,
    ImageRole,
)
from .base import BasePipeline, PipelineOutput


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

        async def get_all_bytes(photos):
            tasks = [
                image_cache.get_cached_image_bytes(
                    p["file_unique_id"], self.cache_pool
                )
                for p in photos
            ]
            results = await asyncio.gather(*tasks)
            return [b for b, _ in results if b is not None]

        father_bytes_list = await get_all_bytes(dad_photos)
        mother_bytes_list = await get_all_bytes(mom_photos)

        await self.update_status_func(_("Preparing parent portraits... 🖼️"))
        
        # Run collage creation in parallel
        collage_tasks = [
            asyncio.to_thread(photo_processing.create_portrait_collage_from_bytes, mother_bytes_list),
            asyncio.to_thread(photo_processing.create_portrait_collage_from_bytes, father_bytes_list),
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
            parent_visual_enhancer.get_parent_visual_representation([mom_collage_url], role="mother"),
            parent_visual_enhancer.get_parent_visual_representation([dad_collage_url], role="father"),
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

        mom_final_ref_url, dad_final_ref_url = mom_collage_url, dad_collage_url
        mom_visual_front_uid, mom_visual_side_uid = None, None
        dad_visual_front_uid, dad_visual_side_uid = None, None

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

        eye_description_text = await eye_enhancer.get_eye_description(
            non_resemblance_parent_url=non_resemblance_parent_final_url
        )

        if not eye_description_text:
            self.log.warning("Eye enhancer failed, using fallback description.")
            eye_description_text = "The child has clear, bright eyes."

        quality_level = self.gen_data.get("quality_level", 1)
        tier_config = settings.child_generation.tiers.get(quality_level)
        if not tier_config:
            raise ValueError(
                f"Tier configuration for child_generation level {quality_level} not found."
            )

        hairstyle_descriptions = await hairstyle_enhancer.get_hairstyle_descriptions(
            num_hairstyles=tier_config.count,
            child_age=self.gen_data["child_age"],
            child_gender=self.gen_data["child_gender"],
        )

        if not hairstyle_descriptions or len(hairstyle_descriptions) < tier_config.count:
            self.log.warning(
                "Hairstyle enhancer failed or returned too few styles, using fallback.",
                requested=tier_config.count,
                returned=len(hairstyle_descriptions or []),
            )
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
            "image_urls": [resemblance_parent_final_url],
            "generation_type": GenerationType.CHILD_GENERATION.value,
            **prompt_payload,
        }

        caption = None

        metadata = {
            "mom_collage_uid": mom_collage_uid,
            "dad_collage_uid": dad_collage_uid,
            "mom_visual_front_uid": mom_visual_front_uid,
            "mom_visual_horizontal_uid": mom_visual_horizontal_uid,
            "dad_visual_front_uid": dad_visual_front_uid,
            "dad_visual_horizontal_uid": dad_visual_horizontal_uid,
            "eye_description_text": eye_description_text,
            "hairstyle_descriptions": hairstyle_descriptions,
        }

        return PipelineOutput(
            request_payload=request_payload, caption=caption, metadata=metadata
        )
# aiogram_bot_template/services/pipelines/pair_photo_pipeline/pair_photo.py
import asyncio
import uuid
import numpy as np
from aiogram.utils.i18n import gettext as _
from aiogram_bot_template.services import image_cache, photo_processing, similarity_scorer
from aiogram_bot_template.services.enhancers import parent_visual_enhancer
from aiogram_bot_template.data.settings import settings
from aiogram_bot_template.data.constants import GenerationType, ImageRole
from ..base import BasePipeline, PipelineOutput
from .pair_default import PROMPT_PAIR_DEFAULT


class PairPhotoPipeline(BasePipeline):
    async def prepare_data(self) -> PipelineOutput:
        """
        Prepares data for pair photo generation. This involves:
        1. Creating collages for both parents from their source photos.
        2. Generating enhanced visual representations (front + side views) for both.
        3. Stacking the two visual representations vertically.
        4. Preparing the final prompt and payload for the generation model.
        """
        await self.update_status_func(_("Analyzing facial features... 🧬"))

        photos_collected = self.gen_data.get("photos_collected", [])
        mom_photos = [p for p in photos_collected if p.get("role") == ImageRole.MOTHER.value]
        dad_photos = [p for p in photos_collected if p.get("role") == ImageRole.FATHER.value]

        if not mom_photos or not dad_photos:
            raise ValueError("Could not identify photos for both partners.")

        async def get_all_processed_bytes(photos):
            tasks = [image_cache.get_cached_image_bytes(p["file_unique_id"], self.cache_pool) for p in photos]
            results = await asyncio.gather(*tasks)
            return [b for b, _ in results if b is not None]

        mother_bytes_list = await get_all_processed_bytes(mom_photos)
        father_bytes_list = await get_all_processed_bytes(dad_photos)

        mom_centroid, dad_centroid = await asyncio.gather(
            similarity_scorer.calculate_identity_centroid(mother_bytes_list),
            similarity_scorer.calculate_identity_centroid(father_bytes_list)
        )

        await self.update_status_func(_("Preparing portraits for the AI... 🖼️"))

        collage_tasks = [
            asyncio.to_thread(photo_processing.create_portrait_collage_from_bytes, mother_bytes_list[:4]),
            asyncio.to_thread(photo_processing.create_portrait_collage_from_bytes, father_bytes_list[:4]),
        ]
        mom_collage_bytes, dad_collage_bytes = await asyncio.gather(*collage_tasks)

        request_id_str = self.gen_data.get("request_id", uuid.uuid4().hex)

        mom_collage_uid = f"collage_mom_processed_{request_id_str}"
        await image_cache.cache_image_bytes(
            mom_collage_uid, mom_collage_bytes, "image/jpeg", self.cache_pool
        )
        mom_collage_url = image_cache.get_cached_image_proxy_url(mom_collage_uid)

        dad_collage_uid = f"collage_dad_processed_{request_id_str}"
        await image_cache.cache_image_bytes(
            dad_collage_uid, dad_collage_bytes, "image/jpeg", self.cache_pool
        )
        dad_collage_url = image_cache.get_cached_image_proxy_url(dad_collage_uid)
        

        if not mom_collage_url or not dad_collage_url:
            raise RuntimeError("Failed to create and cache parent collages.")

        await self.update_status_func(_("Creating visual identities... 🧑‍🎨"))

        visual_tasks = [
            parent_visual_enhancer.get_parent_visual_representation(
                mom_collage_url, role="mother", identity_centroid=mom_centroid, cache_pool=self.cache_pool
            ),
            parent_visual_enhancer.get_parent_visual_representation(
                dad_collage_url, role="father", identity_centroid=dad_centroid, cache_pool=self.cache_pool
            ),
        ]
        mom_profile_bytes, dad_profile_bytes = await asyncio.gather(*visual_tasks)

        if not mom_profile_bytes or not dad_profile_bytes:
            raise RuntimeError("Failed to generate visual representations for one or both partners.")

        mom_profile_uid = f"mom_profile_{request_id_str}"
        await image_cache.cache_image_bytes(mom_profile_uid, mom_profile_bytes, "image/jpeg", self.cache_pool)
        dad_profile_uid = f"dad_profile_{request_id_str}"
        await image_cache.cache_image_bytes(dad_profile_uid, dad_profile_bytes, "image/jpeg", self.cache_pool)

        vertical_stack_bytes = photo_processing.stack_two_images(mom_profile_bytes, dad_profile_bytes)
        vertical_stack_uid = f"vertical_two_stack_{request_id_str}"
        await image_cache.cache_image_bytes(vertical_stack_uid, vertical_stack_bytes, "image/jpeg", self.cache_pool)
        vertical_stack_url = image_cache.get_cached_image_proxy_url(vertical_stack_uid)


        quality_level = self.gen_data.get("quality_level", 1)
        tier_config = settings.pair_photo.tiers.get(quality_level)
        if not tier_config:
            raise ValueError(f"Tier configuration for pair_photo level {quality_level} not found.")

        # For this simplified version, we use a single static prompt.
        completed_prompts = [PROMPT_PAIR_DEFAULT] * tier_config.count

        request_payload = {
            "model": tier_config.model,
            "image_urls": [vertical_stack_url],
            "generation_type": GenerationType.PAIR_PHOTO.value,
            "prompt": completed_prompts[0],
            "temperature": 0.5
        }

        metadata = {
            "mom_collage_uid": mom_collage_uid,
            "dad_collage_uid": dad_collage_uid,
            "mom_profile_uid": mom_profile_uid,
            "dad_profile_uid": dad_profile_uid,
            "vertical_stack_uid": vertical_stack_uid,
            "completed_prompts": completed_prompts
        }

        return PipelineOutput(request_payload=request_payload, caption=None, metadata=metadata)
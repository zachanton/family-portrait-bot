# aiogram_bot_template/services/pipelines/pair_photo_pipeline/pair_photo.py
import asyncio
import uuid
import random
import numpy as np
from aiogram.utils.i18n import gettext as _

from aiogram_bot_template.services import image_cache, photo_processing, similarity_scorer
from aiogram_bot_template.services.enhancers import parent_visual_enhancer
from aiogram_bot_template.data.settings import settings
from aiogram_bot_template.data.constants import GenerationType, ImageRole
from ..base import BasePipeline, PipelineOutput
from .pair_default import PROMPT_PAIR_DEFAULT
from . import styles


class PairPhotoPipeline(BasePipeline):
    """
    Pipeline for generating a couple's portrait.
    Supports session reuse by checking for a pre-existing parent composite image.
    """

    async def _prepare_styled_pair_prompts(
        self, parent_front_side_url: str, style_id: str
    ) -> PipelineOutput:
        """
        Private helper to generate styled pair photo prompts using the provided
        parent composite and selected style.
        """
        await self.update_status_func(_("Designing your photoshoot... 🎨"))
        
        quality_level = self.gen_data.get("quality_level", 1)
        tier_config = settings.pair_photo.tiers.get(quality_level)
        if not tier_config:
            raise ValueError(f"Tier configuration for pair_photo level {quality_level} not found.")

        style_info = styles.STYLES.get(style_id)
        if not style_info:
            raise ValueError(f"Style '{style_id}' not found in the style registry.")

        style_module = style_info["module"]
        style_name = style_module.STYLE_NAME
        style_definition = style_module.STYLE_DEFINITION
        framing_options = style_module.FRAMING_OPTIONS
        style_options = style_module.STYLE_OPTIONS

        num_generations = tier_config.count
        
        # Sample N unique scene keys from the framing options.
        # Use random.choices which handles cases where num_generations > len(keys).
        framing_keys = list(framing_options.keys())
        selected_scenes = random.choices(framing_keys, k=num_generations)
        selected_scenes = framing_keys
        self.log.info("framing_keys: ", framing_keys=framing_keys)

        self.log.info("selected_scenes: ", selected_scenes=selected_scenes)      

        completed_prompts = []
        for scene_name in selected_scenes:
            framing_block = framing_options.get(scene_name)
            style_block = style_options.get(scene_name)

            if not framing_block or not style_block:
                self.log.warning("Mismatch between FRAMING and STYLE keys for scene", scene=scene_name)
                # Fallback: use the first available scene
                fallback_key = framing_keys[0]
                framing_block = framing_options[fallback_key]
                style_block = style_options[fallback_key]

            # Fill in the placeholders in the default prompt template
            final_prompt = PROMPT_PAIR_DEFAULT
            final_prompt = final_prompt.replace("{{STYLE_NAME}}", style_name)
            final_prompt = final_prompt.replace("{{STYLE_DEFINITION}}", style_definition)
            final_prompt = final_prompt.replace("{{SCENE_NAME}}", scene_name)
            final_prompt = final_prompt.replace("{{FRAMING_OPTIONS}}", framing_block)
            final_prompt = final_prompt.replace("{{STYLE_OPTIONS}}", style_block)
            completed_prompts.append(final_prompt)

        request_payload = {
            "model": tier_config.model,
            "image_urls": [ parent_front_side_url ],
            "generation_type": GenerationType.PAIR_PHOTO.value,
            "prompt": completed_prompts[0],  # Use the first as a representative prompt
            "temperature": 0.5,
            "aspect_ratio": '9:16',
        }

        metadata = {"completed_prompts": completed_prompts}
        return PipelineOutput(request_payload=request_payload, caption=None, metadata=metadata)

    async def prepare_data(self) -> PipelineOutput:
        """
        Prepares data for pair photo generation. Checks for existing session data first.
        """
        selected_style_id = self.gen_data.get("pair_photo_style")
        if not selected_style_id:
            raise ValueError("Pair photo style ID is missing from FSM data.")

        # --- Session Reuse Logic ---
        if "parent_front_side_uid" in self.gen_data:
            self.log.info("Reusing existing parent composite for session action.")
            parent_front_side_uid = self.gen_data["parent_front_side_uid"]
            mom_front_dad_front_uid = self.gen_data["mom_front_dad_front_uid"]
            mom_front_dad_side_uid = self.gen_data["mom_front_dad_side_uid"]
            dad_front_mom_side_uid = self.gen_data["dad_front_mom_side_uid"]
            
            output = await self._prepare_styled_pair_prompts(parent_front_side_url, selected_style_id)
            output.metadata["mom_front_dad_front_uid"] = mom_front_dad_front_uid
            output.metadata["mom_front_dad_side_uid"] = mom_front_dad_side_uid
            output.metadata["dad_front_mom_side_uid"] = dad_front_mom_side_uid
            output.metadata["parent_front_side_uid"] = parent_front_side_uid
            output.metadata["processed_uids"] = [ parent_front_side_uid ]
            return output
        
        # --- This block runs only on the first generation in a session ---
        self.log.info("No session data found. Performing full initial setup for pair photo.")
        await self.update_status_func(_("Analyzing facial features... 🧬"))

        photos_collected = self.gen_data.get("photos_collected", [])
        mom_photos = [p for p in photos_collected if p.get("role") == ImageRole.MOTHER.value]
        dad_photos = [p for p in photos_collected if p.get("role") == ImageRole.FATHER.value]

        if not mom_photos or not dad_photos:
            raise ValueError("Could not identify photos for both partners.")

        async def get_all_processed_bytes(photos):
            tasks = [image_cache.get_cached_image_bytes(p["file_unique_id"], self.cache_pool) for p in photos]
            results = await asyncio.gather(*tasks)
            return [b for b, a in results if b is not None]

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
        mom_collage_uid = f"collage_mom_proc_{request_id_str}"
        await image_cache.cache_image_bytes(mom_collage_uid, mom_collage_bytes, "image/jpeg", self.cache_pool)
        mom_collage_url = image_cache.get_cached_image_proxy_url(mom_collage_uid)

        dad_collage_uid = f"collage_dad_proc_{request_id_str}"
        await image_cache.cache_image_bytes(dad_collage_uid, dad_collage_bytes, "image/jpeg", self.cache_pool)
        dad_collage_url = image_cache.get_cached_image_proxy_url(dad_collage_uid)
        
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

        mom_front_bytes, mom_side_bytes = photo_processing.split_and_stack_image_bytes(mom_profile_bytes)
        dad_front_bytes, dad_side_bytes = photo_processing.split_and_stack_image_bytes(dad_profile_bytes)

        mom_profile_uid = f"mom_profile_{request_id_str}"
        await image_cache.cache_image_bytes(mom_profile_uid, mom_profile_bytes, "image/jpeg", self.cache_pool)
        dad_profile_uid = f"dad_profile_{request_id_str}"
        await image_cache.cache_image_bytes(dad_profile_uid, dad_profile_bytes, "image/jpeg", self.cache_pool)

        mom_front_dad_front_bytes = photo_processing.stack_images_horizontally(mom_front_bytes, dad_front_bytes)
        mom_front_dad_front_uid = f"mom_front_dad_front_{request_id_str}"
        await image_cache.cache_image_bytes(mom_front_dad_front_uid, mom_front_dad_front_bytes, "image/jpeg", self.cache_pool)
        mom_front_dad_front_url = image_cache.get_cached_image_proxy_url(mom_front_dad_front_uid)

        mom_front_dad_side_bytes = photo_processing.stack_images_horizontally(mom_front_bytes, dad_side_bytes)
        mom_front_dad_side_uid = f"mom_front_dad_side_{request_id_str}"
        await image_cache.cache_image_bytes(mom_front_dad_side_uid, mom_front_dad_side_bytes, "image/jpeg", self.cache_pool)
        mom_front_dad_side_url = image_cache.get_cached_image_proxy_url(mom_front_dad_side_uid)

        dad_front_mom_side_bytes = photo_processing.stack_images_horizontally(dad_front_bytes, mom_side_bytes)
        dad_front_mom_side_uid = f"dad_front_mom_side_{request_id_str}"
        await image_cache.cache_image_bytes(dad_front_mom_side_uid, dad_front_mom_side_bytes, "image/jpeg", self.cache_pool)
        dad_front_mom_side_url = image_cache.get_cached_image_proxy_url(dad_front_mom_side_uid)

        parent_front_side_bytes = photo_processing.stack_two_images(mom_profile_bytes, dad_profile_bytes)
        parent_front_side_uid = f"parent_front_side_{request_id_str}"
        await image_cache.cache_image_bytes(parent_front_side_uid, parent_front_side_bytes, "image/jpeg", self.cache_pool)
        parent_front_side_url = image_cache.get_cached_image_proxy_url(parent_front_side_uid)

        output = await self._prepare_styled_pair_prompts(parent_front_side_url, selected_style_id)
        
        output.metadata.update({
            "mom_collage_uid": mom_collage_uid,
            "mom_profile_uid": mom_profile_uid,
            "dad_collage_uid": dad_collage_uid,
            "dad_profile_uid": dad_profile_uid,
            "mom_front_dad_front_uid": mom_front_dad_front_uid,
            "mom_front_dad_side_uid": mom_front_dad_side_uid,
            "dad_front_mom_side_uid": dad_front_mom_side_uid,
            "parent_front_side_uid": parent_front_side_uid,
            "processed_uids": [ parent_front_side_uid ]
        })
        
        return output
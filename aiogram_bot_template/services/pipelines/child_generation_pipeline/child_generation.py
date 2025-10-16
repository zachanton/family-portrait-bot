# aiogram_bot_template/services/pipelines/child_generation_pipeline/child_generation.py
import asyncio
import uuid
import random
import numpy as np
from typing import List
from aiogram.utils.i18n import gettext as _
from aiogram_bot_template.services import image_cache, photo_processing
from aiogram_bot_template.services import similarity_scorer
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
from aiogram_bot_template.services.pipelines import PROMPT_CHILD_DEFAULT
from aiogram_bot_template.services.photo_processing_manager import PhotoProcessingManager


class ChildGenerationPipeline(BasePipeline):
    """
    Pipeline for generating a portrait of a potential child.
    Supports session reuse by checking for a pre-existing parent composite image.
    """
    
    def __init__(self, *args, photo_manager: PhotoProcessingManager, **kwargs):
        super().__init__(*args, **kwargs)
        self.photo_manager = photo_manager

    async def _prepare_child_prompts(self, mom_front_dad_front_url: str, mom_front_dad_side_url: str, dad_front_mom_side_url: str) -> PipelineOutput:
        """
        Private helper to generate child prompts using the provided parent composite image.
        This is the part of the logic that runs regardless of session state.
        """
        await self.update_status_func(_("Designing child's features... ✨"))

        quality_level = self.gen_data.get("quality_level", 1)
        tier_config = settings.child_generation.tiers.get(quality_level)
        if not tier_config:
            raise ValueError(f"Tier configuration for child_generation level {quality_level} not found.")
        
        generation_count = tier_config.count
        
        user_resemblance_choice = self.gen_data["child_resemblance"]
        resemblance_list: List[str] = []
        if user_resemblance_choice == ChildResemblance.MOM.value:
            resemblance_list = [ChildResemblance.MOM.value] * generation_count
        elif user_resemblance_choice == ChildResemblance.DAD.value:
            resemblance_list = [ChildResemblance.DAD.value] * generation_count
        else: # ChildResemblance.BOTH
            resemblance_list = [random.choice([ChildResemblance.MOM.value, ChildResemblance.DAD.value]) for a in range(generation_count)]


        feature_details = await child_prompt_enhancer.get_enhanced_child_features(
            parent_composite_url=mom_front_dad_front_url,
            num_variations=generation_count,
            child_age=self.gen_data["child_age"],
            child_gender=self.gen_data["child_gender"],
        )

        if not feature_details:
            self.log.error("Child prompt enhancer failed. Cannot proceed with generation.")
            raise RuntimeError("Failed to generate child prompts.")

        completed_prompts: List[str] = []
        image_reference_list: List[str] = []
        child_role = "daughter" if self.gen_data["child_gender"].lower() == "girl" else "son"
        parental_analysis = feature_details.parental_analysis
        
        hair_colors = { ChildResemblance.MOM.value: parental_analysis.mother_hair_color, ChildResemblance.DAD.value: parental_analysis.father_hair_color}
        eye_colors = { ChildResemblance.MOM.value: parental_analysis.mother_eye_color, ChildResemblance.DAD.value: parental_analysis.father_eye_color}
        for i in range(generation_count):
            creative_variation = feature_details.child_variations[i]
            resemblance_parent = resemblance_list[i]
            non_resemblance_parent = (
                ChildResemblance.DAD.value if resemblance_parent == ChildResemblance.MOM.value else ChildResemblance.MOM.value
            )

            if random.random()<0.66:
                selected_hair_color = hair_colors[resemblance_parent]
            else:
                selected_hair_color = hair_colors[non_resemblance_parent]

            if random.random()<0.66:
                selected_eye_color = eye_colors[resemblance_parent]
            else:
                selected_eye_color = eye_colors[non_resemblance_parent]
            
            if selected_hair_color == parental_analysis.mother_hair_color:
                selected_hair_color = f"10 shades lighter than the mothers' {selected_hair_color.lower()}"
            else:
                selected_hair_color = f"10 shades lighter than the fathers' {selected_hair_color.lower()}"

            if selected_eye_color == parental_analysis.mother_eye_color:
                selected_eye_color = f"mothers' {selected_eye_color.lower()}"
            else:
                selected_eye_color = f"fathers' {selected_eye_color.lower()}"

            final_prompt = PROMPT_CHILD_DEFAULT
            final_prompt = final_prompt.replace("{{CHILD_AGE}}", self.gen_data["child_age"])
            final_prompt = final_prompt.replace("{{CHILD_GENDER}}", self.gen_data["child_gender"])
            final_prompt = final_prompt.replace("{{CHILD_ROLE}}", child_role)
            final_prompt = final_prompt.replace("{{PARENT_A}}", resemblance_parent)
            final_prompt = final_prompt.replace("{{PARENT_B}}", non_resemblance_parent)
            final_prompt = final_prompt.replace("{{SKIN_TONE_ETHNICITY_DESCRIPTION}}", parental_analysis.child_skin_tone_and_ethnicity_description)
            final_prompt = final_prompt.replace("{{HAIRSTYLE_DESCRIPTION}}", creative_variation.hairstyle_description)
            final_prompt = final_prompt.replace("{{HAIR_COLOR_DESCRIPTION}}", selected_hair_color)
            final_prompt = final_prompt.replace("{{EYE_COLOR_DESCRIPTION}}", selected_eye_color)
            
            completed_prompts.append(final_prompt)

            image_reference = mom_front_dad_side_url if resemblance_parent == ChildResemblance.MOM.value else dad_front_mom_side_url
            image_reference_list.append(image_reference)
        
        request_payload = {
            "model": tier_config.model,
            "image_urls": image_reference_list[0],
            "generation_type": GenerationType.CHILD_GENERATION.value,
            "prompt": completed_prompts[0], # Base prompt for logging
            "temperature": 0.9,
            "aspect_ratio":'9:16',
        }
        
        metadata = { "completed_prompts": completed_prompts, 'image_reference_list': image_reference_list }
        return PipelineOutput(request_payload=request_payload, caption=None, metadata=metadata)

    async def prepare_data(self) -> PipelineOutput:
        """
        Prepares data for child generation. Checks for existing session data first.
        """
        if "parent_front_side_uid" in self.gen_data:
            self.log.info("Reusing existing parent composite for session action.")
            parent_front_side_uid = self.gen_data["parent_front_side_uid"]
            mom_front_dad_front_uid = self.gen_data["mom_front_dad_front_uid"]
            mom_front_dad_side_uid = self.gen_data["mom_front_dad_side_uid"]
            dad_front_mom_side_uid = self.gen_data["dad_front_mom_side_uid"]

            mom_front_dad_front_url = image_cache.get_cached_image_proxy_url(mom_front_dad_front_uid)
            mom_front_dad_side_url = image_cache.get_cached_image_proxy_url(mom_front_dad_side_uid)
            dad_front_mom_side_url = image_cache.get_cached_image_proxy_url(dad_front_mom_side_uid)
            
            output = await self._prepare_child_prompts(mom_front_dad_front_url, mom_front_dad_side_url, dad_front_mom_side_url)
            output.metadata["mom_front_dad_front_uid"] = mom_front_dad_front_uid
            output.metadata["mom_front_dad_side_uid"] = mom_front_dad_side_uid
            output.metadata["dad_front_mom_side_uid"] = dad_front_mom_side_uid
            output.metadata["parent_front_side_uid"] = parent_front_side_uid
            output.metadata["processed_uids"] = [ mom_front_dad_front_uid, mom_front_dad_side_uid, dad_front_mom_side_uid ]
            # Also pass collage UIDs for session consistency
            output.metadata["mother_collage_uid"] = self.gen_data.get("mother_collage_uid")
            output.metadata["father_collage_uid"] = self.gen_data.get("father_collage_uid")
            return output

        self.log.info("No session data found. Performing full initial setup for child generation.")
        await self.update_status_func(_("Analyzing parental features... 🧬"))

        photos_collected = self.gen_data.get("photos_collected", [])
        mom_photos = [p for p in photos_collected if p.get("role") == ImageRole.MOTHER.value]
        dad_photos = [p for p in photos_collected if p.get("role") == ImageRole.FATHER.value]
        
        mom_collage_uid = self.gen_data.get("mother_collage_uid")
        dad_collage_uid = self.gen_data.get("father_collage_uid")

        if not mom_collage_uid or not dad_collage_uid:
            raise ValueError("Could not find parent collage UIDs in state.")
        
        mom_collage_url = image_cache.get_cached_image_proxy_url(mom_collage_uid)
        dad_collage_url = image_cache.get_cached_image_proxy_url(dad_collage_uid)

        # Calculate centroids (still needed for visual enhancer)
        async def get_all_processed_bytes(photos):
            tasks = [image_cache.get_cached_image_bytes(p["file_unique_id"], self.cache_pool) for p in photos]
            results = await asyncio.gather(*tasks)
            return [b for b, a in results if b is not None]

        mother_bytes_list = await get_all_processed_bytes(mom_photos)
        father_bytes_list = await get_all_processed_bytes(dad_photos)
        
        mom_centroid, dad_centroid = await asyncio.gather(
            self.photo_manager.calculate_identity_centroid(mother_bytes_list),
            self.photo_manager.calculate_identity_centroid(father_bytes_list)
        )
        
        await self.update_status_func(_("Creating visual identities for the AI... 🧑‍🎨"))

        visual_tasks = [
            parent_visual_enhancer.get_parent_visual_representation(
                mom_collage_url, role="mother", identity_centroid=mom_centroid, cache_pool=self.cache_pool
            ),
            parent_visual_enhancer.get_parent_visual_representation(
                dad_collage_url, role="father", identity_centroid=dad_centroid, cache_pool=self.cache_pool
            ),
        ]
        mom_profile_bytes, dad_profile_bytes = await asyncio.gather(*visual_tasks)
        
        request_id_str = self.gen_data.get("request_id", uuid.uuid4().hex)

        mom_profile_uid = f"mom_profile_{request_id_str}"
        await image_cache.cache_image_bytes(mom_profile_uid, mom_profile_bytes, "image/jpeg", self.cache_pool)
        dad_profile_uid = f"dad_profile_{request_id_str}"
        await image_cache.cache_image_bytes(dad_profile_uid, dad_profile_bytes, "image/jpeg", self.cache_pool)

        mom_front_bytes, mom_side_bytes = photo_processing.split_and_stack_image_bytes(mom_profile_bytes)
        dad_front_bytes, dad_side_bytes = photo_processing.split_and_stack_image_bytes(dad_profile_bytes)

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

        output = await self._prepare_child_prompts(mom_front_dad_front_url, mom_front_dad_side_url, dad_front_mom_side_url)
        
        output.metadata.update({
            "mother_collage_uid": mom_collage_uid,
            "dad_collage_uid": dad_collage_uid,
            "mom_profile_uid": mom_profile_uid,
            "dad_profile_uid": dad_profile_uid,
            "mom_front_dad_front_uid": mom_front_dad_front_uid,
            "mom_front_dad_side_uid": mom_front_dad_side_uid,
            "dad_front_mom_side_uid": dad_front_mom_side_uid,
            "parent_front_side_uid": parent_front_side_uid,
            "processed_uids": [ mom_front_dad_front_uid, mom_front_dad_side_uid, dad_front_mom_side_uid ]
        })
        
        return output
# aiogram_bot_template/services/pipelines/child_generation_pipeline/child_generation.py
import asyncio
import uuid
import random
import numpy as np
from typing import List
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
from aiogram_bot_template.services.pipelines import PROMPT_CHILD_DEFAULT


class ChildGenerationPipeline(BasePipeline):
    """
    Pipeline for generating a portrait of a potential child.
    Supports session reuse by checking for a pre-existing parent composite image.
    """

    async def _prepare_child_prompts(self, parent_composite_url: str) -> PipelineOutput:
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
            parent_composite_url=parent_composite_url,
            num_variations=generation_count,
            child_age=self.gen_data["child_age"],
            child_gender=self.gen_data["child_gender"],
        )

        if not feature_details:
            self.log.error("Child prompt enhancer failed. Cannot proceed with generation.")
            raise RuntimeError("Failed to generate child prompts.")

        completed_prompts = []
        child_role = "daughter" if self.gen_data["child_gender"].lower() == "girl" else "son"
        parental_analysis = feature_details.parental_analysis
        
        for i in range(generation_count):
            creative_variation = feature_details.child_variations[i]
            resemblance_parent = resemblance_list[i]
            non_resemblance_parent = (
                ChildResemblance.DAD.value if resemblance_parent == ChildResemblance.MOM.value else ChildResemblance.MOM.value
            )
            
            selected_hair_color = random.choice([parental_analysis.mother_hair_color, parental_analysis.father_hair_color])
            selected_eye_color = random.choice([parental_analysis.mother_eye_color, parental_analysis.father_eye_color])

            if selected_hair_color == parental_analysis.mother_hair_color:
                selected_hair_color = f"mothers' {selected_hair_color}, a few shades lighter than the mothers' hair."
            else:
                selected_hair_color = f"fathers' {selected_hair_color}, a few shades lighter than the fathers' hair."

            if selected_eye_color == parental_analysis.mother_eye_color:
                selected_eye_color = f"mothers' {selected_eye_color}."
            else:
                selected_eye_color = f"fathers' {selected_eye_color}."

            final_prompt = PROMPT_CHILD_DEFAULT
            final_prompt = final_prompt.replace("{{CHILD_AGE}}", self.gen_data["child_age"])
            final_prompt = final_prompt.replace("{{CHILD_GENDER}}", self.gen_data["child_gender"])
            final_prompt = final_prompt.replace("{{CHILD_ROLE}}", child_role)
            final_prompt = final_prompt.replace("{{PARENT_A}}", resemblance_parent)
            final_prompt = final_prompt.replace("{{PARENT_B}}", non_resemblance_parent)
            final_prompt = final_prompt.replace("{{HAIRSTYLE_DESCRIPTION}}", creative_variation.hairstyle_description)
            final_prompt = final_prompt.replace("{{HAIR_COLOR_DESCRIPTION}}", selected_hair_color)
            final_prompt = final_prompt.replace("{{EYE_COLOR_DESCRIPTION}}", selected_eye_color)
            completed_prompts.append(final_prompt)
        
        request_payload = {
            "model": tier_config.model,
            "image_urls": [parent_composite_url],
            "generation_type": GenerationType.CHILD_GENERATION.value,
            "prompt": completed_prompts[0], # Base prompt for logging
            "temperature": 0.3,
        }
        
        metadata = { "completed_prompts": completed_prompts }
        return PipelineOutput(request_payload=request_payload, caption=None, metadata=metadata)

    async def prepare_data(self) -> PipelineOutput:
        """
        Prepares data for child generation. Checks for existing session data first.
        """
        if "parent_composite_uid" in self.gen_data:
            self.log.info("Reusing existing parent composite for session action.")
            parent_composite_uid = self.gen_data["parent_composite_uid"]
            parent_composite_url = image_cache.get_cached_image_proxy_url(parent_composite_uid)
            
            # Jump directly to the child-specific prompt generation
            output = await self._prepare_child_prompts(parent_composite_url)
            # Add the reused UID to metadata so the worker can find it for debug logs
            output.metadata["parent_composite_uid"] = parent_composite_uid
            output.metadata["processed_uids"] = [parent_composite_uid]
            return output

        # --- This block runs only on the first generation in a session ---
        self.log.info("No session data found. Performing full initial setup for child generation.")
        await self.update_status_func(_("Analyzing parental features... 🧬"))

        photos_collected = self.gen_data.get("photos_collected", [])
        mom_photos = [p for p in photos_collected if p.get("role") == ImageRole.MOTHER.value]
        dad_photos = [p for p in photos_collected if p.get("role") == ImageRole.FATHER.value]

        if not mom_photos or not dad_photos:
            raise ValueError("Could not identify Mom or Dad's photos.")

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

        await self.update_status_func(_("Preparing parent portraits... 🖼️"))
        
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
        dad_collage_url = image_cache.get_cached_image_proxy_url(dad_collage_url)

        await self.update_status_func(_("Creating visual representations of parents... 🧑‍🎨"))

        visual_tasks = [
            parent_visual_enhancer.get_parent_visual_representation(
                mom_collage_url, role="mother", identity_centroid=mom_centroid, cache_pool=self.cache_pool
            ),
            parent_visual_enhancer.get_parent_visual_representation(
                dad_collage_url, role="father", identity_centroid=dad_centroid, cache_pool=self.cache_pool
            ),
        ]
        mom_profile_bytes, dad_profile_bytes = await asyncio.gather(*visual_tasks)

        mom_profile_uid = f"mom_profile_{request_id_str}"
        await image_cache.cache_image_bytes(mom_profile_uid, mom_profile_bytes, "image/jpeg", self.cache_pool)
        dad_profile_uid = f"dad_profile_{request_id_str}"
        await image_cache.cache_image_bytes(dad_profile_uid, dad_profile_bytes, "image/jpeg", self.cache_pool)

        parent_composite_bytes = photo_processing.stack_two_images(mom_profile_bytes, dad_profile_bytes)
        parent_composite_uid = f"parent_composite_{request_id_str}"
        await image_cache.cache_image_bytes(parent_composite_uid, parent_composite_bytes, "image/jpeg", self.cache_pool)
        parent_composite_url = image_cache.get_cached_image_proxy_url(parent_composite_uid)

        output = await self._prepare_child_prompts(parent_composite_url)
        
        # Add all intermediate UIDs to metadata for debugging and session saving
        output.metadata.update({
            "mom_collage_uid": mom_collage_uid,
            "dad_collage_uid": dad_collage_uid,
            "mom_profile_uid": mom_profile_uid,
            "dad_profile_uid": dad_profile_uid,
            "parent_composite_uid": parent_composite_uid,
            "processed_uids": [parent_composite_uid]
        })
        
        return output
# aiogram_bot_template/services/pipelines/family_photo_pipeline/family_photo.py
import asyncio
import uuid
import random
from aiogram.utils.i18n import gettext as _

from aiogram_bot_template.services import image_cache, photo_processing
from aiogram_bot_template.data.settings import settings
from aiogram_bot_template.data.constants import GenerationType, ImageRole
from ..base import BasePipeline, PipelineOutput
from .family_default import PROMPT_FAMILY_DEFAULT
from . import styles as family_styles

class FamilyPhotoPipeline(BasePipeline):
    
    async def prepare_data(self) -> PipelineOutput:
        """
        Prepares data for family photo generation, including style selection and prompt assembly.
        """
        selected_style_id = self.gen_data.get("family_photo_style")
        if not selected_style_id:
            raise ValueError("Family photo style ID is missing from FSM data.")

        await self.update_status_func(_("Preparing your family portrait... 👨‍👩‍👧"))
        
        photos_collected = self.gen_data.get("photos_collected", [])
        if len(photos_collected) < 3:
            raise ValueError(f"Missing source images. Expected 3, got {len(photos_collected)}")
        
        father_photo = next((p for p in photos_collected if p.get("role") == ImageRole.FATHER.value), None)
        mother_photo = next((p for p in photos_collected if p.get("role") == ImageRole.MOTHER.value), None)
        child_photo = next((p for p in photos_collected if p.get("role") == ImageRole.CHILD.value), None)

        if not all([father_photo, mother_photo, child_photo]):
            raise ValueError("Could not identify all roles (father, mother, child) in source images.")

        async def get_bytes(photo_info):
            if not photo_info or not photo_info.get('file_unique_id'):
                return None
            bytes_tuple = await image_cache.get_cached_image_bytes(photo_info['file_unique_id'], self.cache_pool)
            return bytes_tuple[0]

        mother_bytes, father_bytes, child_bytes = await asyncio.gather(
            get_bytes(mother_photo),
            get_bytes(father_photo),
            get_bytes(child_photo)
        )

        if not all([mother_bytes, father_bytes, child_bytes]):
            raise ValueError("Could not retrieve all necessary image bytes from cache.")

        await self.update_status_func(_("Creating family composite for the AI... 🖼️"))
        
        request_id_str = self.gen_data.get('request_id', uuid.uuid4().hex)
        
        composite_bytes = photo_processing.stack_three_images(mother_bytes, father_bytes, child_bytes)
        composite_uid = f"family_composite_{request_id_str}"
        await image_cache.cache_image_bytes(composite_uid, composite_bytes, "image/jpeg", self.cache_pool)
        composite_url = image_cache.get_cached_image_proxy_url(composite_uid)

        # --- Style and Prompt Generation Logic ---
        await self.update_status_func(_("Designing your photoshoot... 🎨"))
        
        quality_level = self.gen_data.get("quality_level", 1)
        tier_config = settings.family_photo.tiers.get(quality_level)
        if not tier_config:
            raise ValueError(f"Tier configuration for family_photo level {quality_level} not found.")

        style_info = family_styles.STYLES.get(selected_style_id)
        if not style_info:
            raise ValueError(f"Style '{selected_style_id}' not found in the family style registry.")

        style_module = style_info["module"]
        style_name = style_module.STYLE_NAME
        style_definition = style_module.STYLE_DEFINITION
        framing_options = style_module.FRAMING_OPTIONS
        style_options = style_module.STYLE_OPTIONS
        num_generations = tier_config.count
        
        framing_keys = list(framing_options.keys())
        selected_scenes = random.choices(framing_keys, k=num_generations)
        
        completed_prompts = []
        for scene_name in selected_scenes:
            framing_block = framing_options.get(scene_name, framing_options[framing_keys[0]])
            style_block = style_options.get(scene_name, style_options[framing_keys[0]])

            final_prompt = PROMPT_FAMILY_DEFAULT
            final_prompt = final_prompt.replace("{{STYLE_NAME}}", style_name)
            final_prompt = final_prompt.replace("{{STYLE_DEFINITION}}", style_definition)
            final_prompt = final_prompt.replace("{{SCENE_NAME}}", scene_name)
            final_prompt = final_prompt.replace("{{FRAMING_OPTIONS}}", framing_block)
            final_prompt = final_prompt.replace("{{STYLE_OPTIONS}}", style_block)
            completed_prompts.append(final_prompt)

        request_payload = {
            "model": tier_config.model,
            "image_urls": [composite_url],
            "generation_type": GenerationType.FAMILY_PHOTO.value,
            "prompt": completed_prompts[0],
            "temperature": 0.5,
            "aspect_ratio": '9:16',
        }
        
        metadata = { 
            "processed_uids": [ composite_uid ],
            "completed_prompts": completed_prompts
        }

        return PipelineOutput(request_payload=request_payload, caption=None, metadata=metadata)
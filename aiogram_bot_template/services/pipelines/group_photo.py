# aiogram_bot_template/services/pipelines/group_photo.py
import random
import uuid
from aiogram.utils.i18n import gettext as _
from aiogram_bot_template.services import image_cache
from aiogram_bot_template.data.settings import settings
from aiogram_bot_template.services.prompting.factory import get_prompt_strategy
from aiogram_bot_template.services import photo_processing
from .base import BasePipeline, PipelineOutput

class GroupPhotoPipeline(BasePipeline):
    async def prepare_data(self) -> PipelineOutput:
        await self.update_status_func("Preparing your group portrait... 👨‍👩‍👧")

        photos_collected = self.gen_data.get("photos_collected", [])
        if len(photos_collected) < 2:
            raise ValueError("Missing one or both source images for group photo.")

        photo1_uid = photos_collected[0].get("processed_files", {}).get("half_body")
        photo2_uid = photos_collected[1].get("processed_files", {}).get("half_body")

        if not photo1_uid or not photo2_uid:
            raise ValueError("Missing processed file unique ID for one or both images.")

        await self.update_status_func("Harmonizing photos... ✨")
        photo1_bytes, _c1 = await image_cache.get_cached_image_bytes(photo1_uid, self.cache_pool)
        photo2_bytes, _c2 = await image_cache.get_cached_image_bytes(photo2_uid, self.cache_pool)

        if not photo1_bytes or not photo2_bytes:
            raise ValueError("Could not retrieve images for harmonization.")

        harmonized1_bytes, harmonized2_bytes = photo_processing.harmonize_pair(photo1_bytes, photo2_bytes)
        
        # --- ДОБАВЛЯЕМ КЕШИРОВАНИЕ ГАРМОНИЗИРОВАННЫХ ФОТО ---
        harmonized1_uid = f"harmonized_{uuid.uuid4().hex}"
        harmonized2_uid = f"harmonized_{uuid.uuid4().hex}"
        await image_cache.cache_image_bytes(harmonized1_uid, harmonized1_bytes, "image/jpeg", self.cache_pool)
        await image_cache.cache_image_bytes(harmonized2_uid, harmonized2_bytes, "image/jpeg", self.cache_pool)

        await self.update_status_func("Creating a composite draft... 🖼️")
        composite_bytes = photo_processing.create_composite_image(harmonized1_bytes, harmonized2_bytes)
        composite_uid = f"composite_{uuid.uuid4().hex}"
        await image_cache.cache_image_bytes(composite_uid, composite_bytes, "image/jpeg", self.cache_pool)
        self.log.info("Cached composite image", uid=composite_uid)
        
        image_urls = [image_cache.get_cached_image_proxy_url(composite_uid)]

        quality_level = self.gen_data.get("quality_level", 1)
        tier_config = settings.group_photo.tiers.get(quality_level)
        if not tier_config:
            raise ValueError(f"Tier configuration for quality level {quality_level} not found.")

        strategy = get_prompt_strategy(tier_config.client)
        prompt_text = (
            "This is a pre-composited image of two people. Your task is to enhance it into a single, cohesive, "
            "ultra-realistic group portrait. **Primary Goal: Seamless Integration & Realism.** "
            "Refine the image to remove any visible seams or blending artifacts. "
            "Ensure the lighting, shadows, and color grading are consistent across the entire scene, making it look like a single photograph. "
            "**Identity Lock:** Preserve 100% of the facial features and identity of each person from the source composite. Do not alter their faces. "
            "**Final Touches:** Enhance the overall quality to professional-grade photorealism. The final output should be a vertical 4:5 aspect ratio portrait. "
            "Fix any compositional awkwardness if possible. Avoid a 'pasted' or 'collage' look."
        )
        prompt_payload = strategy.create_group_photo_payload()
        prompt_payload["prompt"] = " ".join(prompt_text.replace("\n", " ").split())

        is_retry = self.gen_data.get("is_retry", False)
        seed_to_use = random.randint(0, 2**32 - 1) if is_retry else 42

        request_payload = {
            "model": tier_config.model,
            "image_urls": image_urls,
            "seed": seed_to_use,
            **prompt_payload,
        }
        caption = _("✨ Here is your beautiful group portrait!")
        
        # --- ПЕРЕДАЕМ ВСЕ UID ДЛЯ ОТЛАДКИ ---
        metadata = {
            "harmonized_uids": [harmonized1_uid, harmonized2_uid],
            "composite_uid": composite_uid
        }
        
        return PipelineOutput(request_payload=request_payload, caption=caption, metadata=metadata)
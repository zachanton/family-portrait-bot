# File: aiogram_bot_template/services/pipelines/child_generation.py
import time
import random
from typing import Any
from aiogram.utils.i18n import gettext as _

from .base import BasePipeline, PipelineOutput
from aiogram_bot_template.data.constants import ImageRole
from aiogram_bot_template.services import prompting, image_cache
from aiogram_bot_template.data.settings import settings
from aiogram_bot_template.services.llm_invokers import VisionService, PromptEnhancerService
from aiogram_bot_template.dto.facial_features import ImageDescription
from aiogram_bot_template.data.constants import GenerationType
from aiogram_bot_template.keyboards.inline.quality import _get_translated_quality_name


class ChildGenerationPipeline(BasePipeline):
    """
    Pipeline for generating a child's face from two parent photos.
    It intelligently re-orders parent data to ensure the child resembles the correct parent.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.vision_service = VisionService()
        self.enhancer_service = PromptEnhancerService()

    async def _get_prompt_payload(self, blueprint, user_content=None) -> dict:
        """Helper to get a payload, either from a blueprint's bypass or via the enhancer service."""
        if blueprint.enhancer_bypass_payload is not None:
            self.log.info("Bypassing enhancer service for static blueprint.")
            return blueprint.enhancer_bypass_payload

        prompt_model = await self.enhancer_service.generate_structured_prompt(
            system_prompt=blueprint.system_prompt,
            user_content=user_content or [],
            output_model=blueprint.output_model
        )
        return prompt_model.model_dump(exclude_none=True)

    async def prepare_data(self) -> PipelineOutput:
        """
        Prepares data for child generation by analyzing both parents, determining the primary genetic donor,
        and creating a prompt that instructs the AI model how to blend their features with a strong resemblance.
        """
        age_group = self.gen_data.get("age_group")
        params = {
            "age": {"baby": 2, "child": 6, "teen": 14}.get(age_group),
            "gender": self.gen_data.get("gender"),
            "resemble": self.gen_data.get("resemble"),
        }
        if not all(params.values()):
            raise ValueError(f"Missing required parameters for child generation: {params}")

        quality_level = self.gen_data.get("quality_level", 1)
        source_images_map = {img["role"]: img for img in self.gen_data["source_images"]}

        p1_unique_id = source_images_map[ImageRole.PARENT_1]["file_unique_id"]
        p2_unique_id = source_images_map[ImageRole.PARENT_2]["file_unique_id"]

        # 1. Analyze both parents first to get their gender and features
        parent_descriptions = self.gen_data.get("parent_descriptions")
        if parent_descriptions:
            self.log.info("Retry detected. Using pre-analyzed parent descriptions.")
            p1_desc_data = parent_descriptions.get("parent1")
            p2_desc_data = parent_descriptions.get("parent2")
        else:
            self.log.info("First generation attempt. Analyzing parent images from cache.")
            await self.update_status_func(_("Analyzing first parent... 🧬"))
            p1_desc_data = await self._analyze_parent_image(p1_unique_id)
            await self.update_status_func(_("Analyzing second parent... 🧬"))
            p2_desc_data = await self._analyze_parent_image(p2_unique_id)
            parent_descriptions = {"parent1": p1_desc_data, "parent2": p2_desc_data}

        p1_model = ImageDescription.model_validate(p1_desc_data) if p1_desc_data else None
        p2_model = ImageDescription.model_validate(p2_desc_data) if p2_desc_data else None

        if not (p1_model and p2_model):
            raise ValueError("Failed to get valid facial descriptions for one or both parents.")

        # 2. Determine who is the Primary and Secondary donor based on 'resemble'
        resemble_gender = "female" if params["resemble"] == "mother" else "male"

        primary_model, secondary_model = p1_model, p2_model
        primary_unique_id, secondary_unique_id = p1_unique_id, p2_unique_id

        # Swap if P2 is the one we need to resemble
        if p2_model.gender and p2_model.gender.lower() == resemble_gender:
            primary_model, secondary_model = p2_model, p1_model
            primary_unique_id, secondary_unique_id = p2_unique_id, p1_unique_id

        # 3. Create correctly ordered image URLs for the payload
        primary_url = image_cache.get_cached_image_proxy_url(primary_unique_id)
        secondary_url = image_cache.get_cached_image_proxy_url(secondary_unique_id)
        image_urls = [primary_url, primary_url, secondary_url]

        # 4. Get the strategy and create the blueprint using the correctly ordered models
        generation_type = GenerationType(self.gen_data.get("generation_type"))
        generation_config = getattr(settings, generation_type.value)
        tier_config = generation_config.tiers.get(quality_level, generation_config.tiers[1])
        strategy = prompting.get_prompt_strategy(tier_config.client, tier_config.model)

        await self.update_status_func(_("Merging genetic traits... 🔬"))
        blueprint = strategy.create_child_generation_blueprint(p1=primary_model, p2=secondary_model, **params)

        prompt_payload = await self._get_prompt_payload(blueprint)

        is_retry = self.gen_data.get("is_retry", False)
        seed_to_use = random.randint(0, 2**32 - 1) if is_retry else 42

        request_payload = {
            "model": tier_config.model,
            "image_urls": image_urls,
            "seed": seed_to_use,
            **prompt_payload,
        }

        quality_name = _get_translated_quality_name(quality_level)
        caption = _("✨ Ta-da! Here's a little glimpse into the future. I hope you love it! (Quality: {quality})").format(quality=quality_name)

        metadata_to_preserve = {"parent_descriptions": parent_descriptions}
        return PipelineOutput(
            request_payload=request_payload,
            caption=caption,
            metadata=metadata_to_preserve
        )

    async def _analyze_parent_image(self, unique_id: str) -> dict[str, Any] | None:
        """Analyzes a parent image by fetching its bytes from cache."""
        self.log.info("Starting parent image analysis from cache", unique_id=unique_id)
        started = time.monotonic()
        try:
            image_bytes, content_type = await image_cache.get_cached_image_bytes(unique_id, self.cache_pool)
            if not image_bytes or not content_type:
                self.log.error("Image not found in cache", unique_id=unique_id)
                return None

            description: ImageDescription | None = await self.vision_service.analyze_face(
                image_bytes, content_type, image_unique_id=unique_id
            )
            self.log.info(
                "Finished parent analysis",
                duration_ms=int((time.monotonic() - started) * 1000),
            )
            return description.model_dump() if description else None
        except Exception:
            self.log.exception("Parent image analysis failed")
            return None

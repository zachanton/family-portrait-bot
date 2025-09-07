# File: aiogram_bot_template/services/pipelines/group_photo.py
from aiogram.utils.i18n import gettext as _

from .base import BasePipeline, PipelineOutput
from aiogram_bot_template.data.constants import ImageRole
from aiogram_bot_template.services import image_cache, prompting
from aiogram_bot_template.data.settings import settings
from aiogram_bot_template.keyboards.inline.quality import _get_translated_quality_name


class GroupPhotoPipeline(BasePipeline):
    """
    Pipeline for creating a cohesive group portrait from three separate images:
    two parents and one child, using a PromptStrategy.
    """

    async def prepare_data(self) -> PipelineOutput:
        """
        Prepares data for group photo generation by identifying the mother and father,
        ordering the images correctly, and constructing the request payload.
        """
        await self.update_status_func("Preparing your family portrait... 👨‍👩‍👧")
        
        # 1. Map source images from the DB data for easy access
        source_images_map = {img["role"]: img for img in self.gen_data.get("source_images", [])}
        
        # 2. Get parent descriptions to determine gender
        parent_descriptions = self.gen_data.get("parent_descriptions")
        child_uid = source_images_map.get(ImageRole.GROUP_PHOTO_CHILD, {}).get("file_unique_id")

        if not parent_descriptions or not child_uid:
            raise ValueError("Missing parent descriptions or child image for group photo.")

        # 3. Identify mother and father UIDs based on gender from the descriptions
        # The handler ensures that GROUP_PHOTO_PARENT_1 corresponds to the original 'parent1' description
        p1_uid = source_images_map.get(ImageRole.GROUP_PHOTO_PARENT_1, {}).get("file_unique_id")
        p2_uid = source_images_map.get(ImageRole.GROUP_PHOTO_PARENT_2, {}).get("file_unique_id")

        if not p1_uid or not p2_uid:
            raise ValueError("Missing one or both parent images for group photo generation.")
            
        p1_gender = (parent_descriptions.get("parent1", {}).get("gender") or "").lower()
        p2_gender = (parent_descriptions.get("parent2", {}).get("gender") or "").lower()

        mother_uid = p1_uid if p1_gender == "female" else p2_uid
        father_uid = p2_uid if mother_uid == p1_uid else p1_uid

        # Fallback if genders are the same or missing, to prevent errors
        if p1_gender == p2_gender or not p1_gender or not p2_gender:
            self.log.warning(
                "Could not determine distinct mother/father genders, using original upload order.",
                p1_gender=p1_gender, p2_gender=p2_gender
            )
            mother_uid, father_uid = p1_uid, p2_uid

        # 4. Get proxy URLs for the images, in the correct order: Mother, Father, Child
        image_urls = [
            image_cache.get_cached_image_proxy_url(mother_uid),
            image_cache.get_cached_image_proxy_url(father_uid),
            image_cache.get_cached_image_proxy_url(child_uid),
        ]

        # 5. Get model and client configuration from settings
        quality_level = self.gen_data.get("quality_level", 1)
        tier_config = settings.group_photo.tiers.get(quality_level, settings.group_photo.tiers[1])
        client_name = tier_config.client
        model_name = tier_config.model
        
        # 6. Use the strategy factory to get the correct prompting strategy
        strategy = prompting.get_prompt_strategy(client_name, model_name)
        blueprint = strategy.create_group_photo_blueprint()

        if blueprint.enhancer_bypass_payload is None:
            raise NotImplementedError(f"Strategy for {client_name}/{model_name} must use enhancer_bypass_payload for group photos.")
        
        prompt_payload = blueprint.enhancer_bypass_payload

        # 7. Assemble the final request payload
        request_payload = {
            "model": model_name,
            "image_urls": image_urls,
            **prompt_payload,
        }

        # 8. Prepare the user-facing caption and preserve metadata
        quality_name = _get_translated_quality_name(quality_level)
        caption = _("✨ Here is your beautiful family portrait! (Quality: {quality})").format(quality=quality_name)

        metadata_to_preserve = {
            "parent_descriptions": self.gen_data.get("parent_descriptions"),
            "child_description": self.gen_data.get("child_description")
        }

        return PipelineOutput(
            request_payload=request_payload,
            caption=caption,
            metadata=metadata_to_preserve
        )
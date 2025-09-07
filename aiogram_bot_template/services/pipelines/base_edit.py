# File: aiogram_bot_template/services/pipelines/base_edit.py
from abc import abstractmethod
from aiogram.utils.i18n import gettext as _

from .base import BasePipeline, PipelineOutput
from aiogram_bot_template.keyboards.inline.quality import _get_translated_quality_name
from aiogram_bot_template.services import prompting, image_cache
from aiogram_bot_template.data.settings import settings
from aiogram_bot_template.services.llm_invokers import PromptEnhancerService
from aiogram_bot_template.dto.llm_responses import PromptBlueprint


class BaseEditPipeline(BasePipeline):
    """
    An abstract base pipeline for all image editing operations (single and group).
    It handles the common logic of preparing payloads and leaves specific
    details to subclasses.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.enhancer_service = PromptEnhancerService()

    @abstractmethod
    def _get_blueprint(self, strategy: prompting.PromptStrategy) -> PromptBlueprint:
        """Subclasses must implement this to return the correct prompt blueprint."""
        raise NotImplementedError

    @abstractmethod
    def _build_user_content(self, prompt_text: str, image_url: str) -> list[dict]:
        """Subclasses must implement this to build the content for the enhancer."""
        raise NotImplementedError

    @abstractmethod
    def _get_caption(self, original_prompt: str, quality_name: str) -> str:
        """Subclasses must implement this to return the correct final caption."""
        raise NotImplementedError

    async def prepare_data(self) -> PipelineOutput:
        """
        Main preparation logic for all edit pipelines.
        """
        source_image = self.gen_data["photos_collected"][0]
        image_url = image_cache.get_cached_image_proxy_url(source_image["file_unique_id"])

        quality_level = self.gen_data.get("quality_level", 1)
        tier_config = settings.image_edit.tiers.get(quality_level, settings.image_edit.tiers[1])
        strategy = prompting.get_prompt_strategy(tier_config.client, tier_config.model)

        prompt_text = self.gen_data.get("prompt_for_enhancer") or self.gen_data.get("original_prompt_text")
        if not prompt_text:
            raise ValueError("Cannot prepare image edit: no prompt text found in state.")

        await self.update_status_func(_("Rephrasing for the AI... ✍️"))

        blueprint = self._get_blueprint(strategy)
        user_content = self._build_user_content(prompt_text, image_url)

        prompt_payload_model = await self.enhancer_service.generate_structured_prompt(
            system_prompt=blueprint.system_prompt,
            user_content=user_content,
            output_model=blueprint.output_model
        )

        prompt_payload = prompt_payload_model.model_dump(exclude_none=True)

        request_params = {
            "model": tier_config.model,
            "image_url": image_url,
            **prompt_payload,
        }

        final_request_payload = {k: v for k, v in request_params.items() if v is not None}

        original_prompt_for_caption = self.gen_data.get("original_prompt_text", "your edit")
        quality_name = _get_translated_quality_name(quality_level)
        caption = self._get_caption(original_prompt_for_caption, quality_name)

        metadata_to_preserve = {
            "parent_descriptions": self.gen_data.get("parent_descriptions"),
            "child_description": self.gen_data.get("child_description")
        }

        return PipelineOutput(
            request_payload=final_request_payload,
            caption=caption,
            metadata=metadata_to_preserve
        )
# aiogram_bot_template/services/pipelines/upscale.py
from aiogram.utils.i18n import gettext as _

from .base import BasePipeline, PipelineOutput
from aiogram_bot_template.services import image_cache, prompting
from aiogram_bot_template.data.settings import settings
from aiogram_bot_template.services.llm_invokers import PromptEnhancerService
from aiogram_bot_template.data.constants import GenerationType


class UpscalePipeline(BasePipeline):
    """
    A smart upscale pipeline that uses a dedicated model to refine and enhance
    an existing image without changing its core content. It is now aware of the
    source image type to generate context-aware mock prompts.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.enhancer_service = PromptEnhancerService()

    async def prepare_data(self) -> PipelineOutput:
        source_unique_id = self.gen_data["source_images"][0]["file_unique_id"]
        image_url = image_cache.get_cached_image_proxy_url(source_unique_id)

        quality_level = self.gen_data.get("quality_level", 1)

        tier_config = settings.upscale.tiers.get(quality_level, settings.upscale.tiers[1])
        client_name = tier_config.client
        model_name = tier_config.model

        strategy = prompting.get_prompt_strategy(client_name, model_name)

        await self.update_status_func("Preparing HD enhancement... ⚙️")
                
        # This key is now reliably set by the handler based on the session context.
        effective_source_type_str = self.gen_data.get("effective_source_type_for_upscale")
        effective_source_type = GenerationType(effective_source_type_str) if effective_source_type_str else None
        
        self.log.info(
            "Determined upscale context from FSM",
            effective_source=effective_source_type.value if effective_source_type else None,
        )

        blueprint = strategy.create_upscale_blueprint(source_generation_type=effective_source_type)
        
        user_content = [{"type": "image_url", "image_url": {"url": image_url}}]

        prompt_payload_model = await self.enhancer_service.generate_structured_prompt(
            system_prompt=blueprint.system_prompt,
            user_content=user_content,
            output_model=blueprint.output_model
        )

        prompt_payload = prompt_payload_model.model_dump(exclude_none=True)

        request_payload = {
            "model": model_name,
            "image_url": image_url,
        }
        request_payload.update(prompt_payload)

        caption = _("✨ Here is the HD version of your image.")
        metadata_to_preserve = {
            "parent_descriptions": self.gen_data.get("parent_descriptions"),
            "child_description": self.gen_data.get("child_description")
        }

        return PipelineOutput(
            request_payload=request_payload, 
            caption=caption,
            metadata=metadata_to_preserve
        )
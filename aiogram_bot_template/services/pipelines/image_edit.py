# File: aiogram_bot_template/services/pipelines/image_edit.py
from aiogram.utils.i18n import gettext as _

from .base_edit import BaseEditPipeline
from aiogram_bot_template.services import prompting
from aiogram_bot_template.dto.llm_responses import PromptBlueprint


class ImageEditPipeline(BaseEditPipeline):
    """
    Pipeline for editing an existing single-person image based on a text prompt.
    """

    def _get_blueprint(self, strategy: prompting.PromptStrategy) -> PromptBlueprint:
        self.log.info("Creating blueprint for SINGLE image edit.")
        return strategy.create_image_edit_blueprint()

    def _build_user_content(self, prompt_text: str, image_url: str) -> list[dict]:
        """Includes detailed child description for better contextual edits."""
        child_description = self.gen_data.get("child_description")
        return [
            {"type": "text", "text": f"\n**User Request:**\n```{prompt_text}```\n\n**Image Context (JSON Description):**\n```json\n{child_description}\n```"},
            {"type": "image_url", "image_url": {"url": image_url}},
        ]

    def _get_caption(self, original_prompt: str, quality_name: str) -> str:
        return _("✨ Your vision, brought to life! Here is the edited image.\nYour request: «{prompt}» (Quality: {quality})").format(
            prompt=original_prompt, quality=quality_name
        )
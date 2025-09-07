# File: aiogram_bot_template/services/pipelines/group_photo_edit.py
from aiogram.utils.i18n import gettext as _

from .base_edit import BaseEditPipeline
from aiogram_bot_template.services import prompting
from aiogram_bot_template.dto.llm_responses import PromptBlueprint


class GroupPhotoEditPipeline(BaseEditPipeline):
    """
    Pipeline for editing an existing group photo based on a text prompt.
    """

    def _get_blueprint(self, strategy: prompting.PromptStrategy) -> PromptBlueprint:
        self.log.info("Creating blueprint for GROUP PHOTO edit.")
        return strategy.create_group_photo_edit_blueprint()

    def _build_user_content(self, prompt_text: str, image_url: str) -> list[dict]:
        """For group photos, we don't send detailed JSON descriptions yet."""
        return [
            {"type": "text", "text": f"\n**User Request:**\n```{prompt_text}```"},
            {"type": "image_url", "image_url": {"url": image_url}},
        ]

    def _get_caption(self, original_prompt: str, quality_name: str) -> str:
        return _("✨ Here is your edited family portrait!\nYour request: «{prompt}» (Quality: {quality})").format(
            prompt=original_prompt, quality=quality_name
        )
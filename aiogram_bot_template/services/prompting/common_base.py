# aiogram_bot_template/services/prompting/common_base.py
from __future__ import annotations

from .base_strategy import PromptStrategy
from ...dto.facial_features import ImageDescription
from ...dto.llm_responses import PromptBlueprint
from aiogram_bot_template.data.constants import GenerationType
from aiogram_bot_template.dto.llm_responses import (
    SinglePromptOutput
)


class BasePromptStrategy(PromptStrategy):
    """
    Base class for prompt strategies. In this architecture, it primarily serves as a common
    ancestor and ensures all strategies adhere to the PromptStrategy interface.
    All complex logic is delegated to subclasses via their system prompts.
    """

    def create_child_generation_blueprint(
        self, p1: ImageDescription, p2: ImageDescription, age: int, gender: str, resemble: str
    ) -> PromptBlueprint:
        raise NotImplementedError("Child generation blueprints must be defined in a specific strategy.")

    def create_image_edit_blueprint(self) -> PromptBlueprint:
        raise NotImplementedError("Image edit blueprints must be defined in a specific strategy.")

    def create_group_photo_edit_blueprint(self) -> PromptBlueprint:
        raise NotImplementedError("Group photo edit blueprints must be defined in a specific strategy.")

    def create_upscale_blueprint(self, source_generation_type: GenerationType | None = None) -> PromptBlueprint:
        raise NotImplementedError("Upscale blueprints must be defined in a specific strategy.")

    def create_group_photo_blueprint(self) -> PromptBlueprint:
        raise NotImplementedError("Group photo blueprints must be defined in a specific strategy.")
    

class MockStrategy(BasePromptStrategy):
    """
    A mock strategy providing dummy blueprints for all generation types for robust testing.
    """
    def create_child_generation_blueprint(
        self, p1: ImageDescription, p2: ImageDescription, age: int, gender: str, resemble: str
    ) -> PromptBlueprint:
        return PromptBlueprint(
            system_prompt=f"Mock system prompt for a {age}-year-old {gender}, resembling {resemble}.",
            output_model=SinglePromptOutput
        )

    def create_image_edit_blueprint(self) -> PromptBlueprint:
        return PromptBlueprint(
            system_prompt="Mock system prompt for an image edit.",
            output_model=SinglePromptOutput
        )

    def create_group_photo_edit_blueprint(self) -> PromptBlueprint:
        return PromptBlueprint(
            system_prompt="Mock system prompt for a family portrait edit.",
            output_model=SinglePromptOutput
        )

    def create_upscale_blueprint(self, source_generation_type: GenerationType | None = None) -> PromptBlueprint:
        # Now the mock is smart based on the effective source type provided by the pipeline.
        if source_generation_type == GenerationType.GROUP_PHOTO:
            prompt = "Mock system prompt for upscaling a family portrait."
        else:
            prompt = "Mock system prompt for an upscale."
            
        return PromptBlueprint(
            system_prompt=prompt,
            output_model=SinglePromptOutput
        )

    def create_group_photo_blueprint(self) -> PromptBlueprint:
        return PromptBlueprint(
            enhancer_bypass_payload={
                "prompt": "Mock system prompt for a family portrait.",
            }
        )
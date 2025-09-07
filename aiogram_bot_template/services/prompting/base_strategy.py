# aiogram_bot_template/services/prompting/base_strategy.py
from abc import ABC, abstractmethod

from aiogram_bot_template.dto.llm_responses import PromptBlueprint
from aiogram_bot_template.dto.facial_features import ImageDescription
from aiogram_bot_template.data.constants import GenerationType

class PromptStrategy(ABC):
    """
    Abstract base class for a prompt generation strategy.
    Defines the interface for creating model-specific prompt blueprints.
    """

    @abstractmethod
    def create_child_generation_blueprint(
        self, p1: ImageDescription, p2: ImageDescription, age: int, gender: str, resemble: str
    ) -> PromptBlueprint:
        """Creates a blueprint for the prompt enhancer for single-image child generation."""
        raise NotImplementedError

    @abstractmethod
    def create_image_edit_blueprint(self) -> PromptBlueprint:
        """Creates a blueprint for the prompt enhancer for image editing."""
        raise NotImplementedError
    
    @abstractmethod
    def create_group_photo_edit_blueprint(self) -> PromptBlueprint:
        """Creates a blueprint for the prompt enhancer for group photo editing."""
        raise NotImplementedError

    @abstractmethod
    def create_upscale_blueprint(self, source_generation_type: GenerationType | None = None) -> PromptBlueprint:
        """Creates a blueprint for the prompt enhancer for upscaling."""
        raise NotImplementedError

    @abstractmethod
    def create_group_photo_blueprint(self) -> PromptBlueprint:
        """Creates a blueprint for the group photo generation."""
        raise NotImplementedError
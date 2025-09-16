# aiogram_bot_template/services/prompting/base_strategy.py
from abc import ABC, abstractmethod
from typing import Dict, Any

class PromptStrategy(ABC):
    """
    Abstract base class for a prompt generation strategy.
    Defines the interface for creating model-specific prompts and parameters.
    """

    @abstractmethod
    def create_group_photo_payload(self, style: str | None = None) -> Dict[str, Any]:
        """
        Creates the specific prompt and parameters for the initial group photo generation.
        """
        raise NotImplementedError

    @abstractmethod
    def create_group_photo_next_payload(self, style: str | None = None) -> Dict[str, Any]:
        """
        Creates the specific prompt and parameters for a subsequent shot in a photoshoot sequence.
        """
        raise NotImplementedError
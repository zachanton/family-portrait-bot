# aiogram_bot_template/services/prompting/mock_strategy.py
from typing import Dict, Any
from .base_strategy import PromptStrategy

from .styles import (
    PROMPT_DEFAULT,
)
from .fal_strategy import STYLE_PROMPTS, STYLE_PROMPTS_NEXT

class MockStrategy(PromptStrategy):
    """
    A mock strategy providing a dummy payload for robust testing.
    """
    def create_group_photo_payload(self, style: str | None = None) -> Dict[str, Any]:
        prompt = STYLE_PROMPTS.get(style, PROMPT_DEFAULT)
        return {
            "prompt": f"Mock prompt: {prompt}",
            "temperature": 0.3,
        }

    def create_group_photo_next_payload(self, style: str | None = None) -> Dict[str, Any]:
        """
        Creates a mock payload for the 'next shot' generation.
        """
        prompt = STYLE_PROMPTS_NEXT.get(style, PROMPT_DEFAULT)
        return {
            "prompt": f"Mock prompt for next shot: {prompt}",
            "temperature": 0.45,
        }
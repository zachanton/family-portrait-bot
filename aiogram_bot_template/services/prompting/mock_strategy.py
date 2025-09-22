# aiogram_bot_template/services/prompting/mock_strategy.py
from typing import Dict, Any
from .base_strategy import PromptStrategy
from .styles import PROMPT_DEFAULT, PROMPT_FAMILY_DEFAULT
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
        prompt = STYLE_PROMPTS_NEXT.get(style, PROMPT_DEFAULT)
        return {
            "prompt": f"Mock prompt for next shot: {prompt}",
            "temperature": 0.45,
        }
    
    def create_child_generation_payload(
        self, child_gender: str, child_age: str, child_resemblance: str
    ) -> Dict[str, Any]:
        """
        Creates a mock payload for generating a child's portrait.
        """
        prompt = f"Child generation prompt for a {child_age}-year-old {child_gender}."
        return {
            "prompt": f"Mock Child Gen: {prompt}",
            "temperature": 0.4,
        }

    def create_pair_photo_payload(self, style: str | None = None) -> Dict[str, Any]:
        prompt = PROMPT_DEFAULT
        return {
            "prompt": f"Mock Pair Photo Prompt: {prompt}",
            "temperature": 0.3,
        }

    def create_family_photo_payload(self, style: str | None = None) -> Dict[str, Any]:
        prompt = PROMPT_FAMILY_DEFAULT
        return {
            "prompt": f"Mock Family Photo Prompt (3 people): {prompt}",
            "temperature": 0.3,
        }
# aiogram_bot_template/services/prompting/mock_strategy.py
from typing import Dict, Any
from .base_strategy import PromptStrategy
from .styles import PROMPT_DEFAULT
from .styles.child_generation import PROMPT_CHILD_GENERATION
from .fal_strategy import STYLE_PROMPTS, STYLE_PROMPTS_NEXT
from aiogram_bot_template.services.child_feature_enhancer import ChildGenerationHints

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
    
    def create_child_generation_payload(
        self, hints: ChildGenerationHints, gender: str, age: str, resemblance: str
    ) -> Dict[str, Any]:
        """
        Creates the specific prompt and parameters for generating a child's portrait.
        """
        prompt = PROMPT_CHILD_GENERATION
        return {
            "prompt": f"Mock Child Gen: {prompt}",
            "temperature": 0.4,
        }
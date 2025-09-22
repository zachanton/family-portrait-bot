# aiogram_bot_template/services/prompting/mock_strategy.py
from typing import Dict, Any
from pathlib import Path

from aiogram_bot_template.data.constants import ChildAge
from .base_strategy import PromptStrategy
from .styles import PROMPT_DEFAULT, PROMPT_FAMILY_DEFAULT
from .fal_strategy import STYLE_PROMPTS, STYLE_PROMPTS_NEXT

class MockStrategy(PromptStrategy):
    """
    A mock strategy providing a dummy payload for robust testing.
    """
    def _get_child_prompt_template(
        self, age: str, gender: str, resemblance: str
    ) -> str:
        """
        Dynamically loads the correct prompt file based on the child's parameters.
        """
        try:
            age_name = ChildAge(age).name.lower()
        except ValueError:
            if age == "2": age_name = "infant"
            elif age == "7": age_name = "child"
            else: age_name = "teen"

        prompt_path = (
            Path(__file__).parent
            / "styles"
            / "child_generation"
            / age_name
            / gender
            / f"{resemblance}.txt"
        )
        if not prompt_path.exists():
            raise FileNotFoundError(f"Prompt file not found at: {prompt_path}")

        return prompt_path.read_text(encoding="utf-8")
    
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
        prompt = self._get_child_prompt_template(
            age=child_age, gender=child_gender, resemblance=child_resemblance
        )
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
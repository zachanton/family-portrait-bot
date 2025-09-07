# aiogram_bot_template/services/prompting/mock_strategy.py
from typing import Dict, Any
from .base_strategy import PromptStrategy

class MockStrategy(PromptStrategy):
    """
    A mock strategy providing a dummy payload for robust testing.
    """
    def create_group_photo_payload(self) -> Dict[str, Any]:
        return {
            "prompt": "Mock system prompt for a group portrait.",
        }
# aiogram_bot_template/services/prompting/mock_strategy.py
from typing import Dict, Any
from .base_strategy import PromptStrategy

class MockStrategy(PromptStrategy):
    """
    A mock strategy providing a dummy payload for robust testing.
    """
    def create_group_photo_payload(self, style: str | None = None) -> Dict[str, Any]:
        return {
            "prompt": f"Mock system prompt for a group portrait with style: {style}.",
        }
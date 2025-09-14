# aiogram_bot_template/services/prompting/factory.py
from .base_strategy import PromptStrategy
from .fal_strategy import FalStrategy
from .mock_strategy import MockStrategy

STRATEGY_MAP: dict[str, type[PromptStrategy]] = {
    "fal": FalStrategy,
    "mock": MockStrategy,
    "google": FalStrategy,
}

def get_prompt_strategy(client_name: str) -> PromptStrategy:
    """
    Returns the appropriate prompt strategy for the given client name.
    """
    client_lower = client_name.lower()
    
    strategy_class = STRATEGY_MAP.get(client_lower, FalStrategy)
    
    return strategy_class()
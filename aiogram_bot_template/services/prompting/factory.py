# aiogram_bot_template/services/prompting/factory.py

from .base_strategy import PromptStrategy
from .common_base import BasePromptStrategy, MockStrategy
from .cloud import FalFluxStrategy, FalGeminiStrategy, FalRecraftStrategy

STRATEGY_MATRIX: dict[str, dict[str, type[PromptStrategy]]] = {
    "fal": {
        "flux": FalFluxStrategy,
        "gemini": FalGeminiStrategy,
        "recraft": FalRecraftStrategy,
        "default": FalFluxStrategy,
    },
    "mock": {
        "default": MockStrategy
    },
    "default": {
        "default": BasePromptStrategy
    }
}


def get_prompt_strategy(client_name: str, model_name: str) -> PromptStrategy:
    """
    Returns the most specific prompt strategy available for the given client and model.
    """
    client_lower = client_name.lower()
    model_lower = model_name.lower()

    model_family = "flux"  # Default assumption
    if "gemini" in model_lower:
        model_family = "gemini"
    elif "recraft" in model_lower:
        model_family = "recraft"

    provider_strategies = STRATEGY_MATRIX.get(client_lower, STRATEGY_MATRIX["default"])

    strategy_class = provider_strategies.get(model_family)

    if not strategy_class:
        strategy_class = provider_strategies.get("default")

    if not strategy_class:
        strategy_class = STRATEGY_MATRIX["default"]["default"]

    return strategy_class()

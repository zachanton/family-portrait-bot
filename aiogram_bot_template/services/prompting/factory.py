# aiogram_bot_template/services/prompting/factory.py
from .base_strategy import PromptStrategy
from .fal_strategy import FalStrategy
from .mock_strategy import MockStrategy

# Карта, которая сопоставляет имя клиента с классом его стратегии
STRATEGY_MAP: dict[str, type[PromptStrategy]] = {
    "fal": FalStrategy,
    "mock": MockStrategy,
    "google": FalStrategy, # Можно использовать Fal как стратегию по умолчанию
    # Добавьте сюда другие, например: "openai": OpenAIStrategy
}

def get_prompt_strategy(client_name: str) -> PromptStrategy:
    """
    Returns the appropriate prompt strategy for the given client name.
    """
    client_lower = client_name.lower()
    
    # Ищем стратегию в карте, если не находим - используем FalStrategy как запасной вариант
    strategy_class = STRATEGY_MAP.get(client_lower, FalStrategy)
    
    return strategy_class()
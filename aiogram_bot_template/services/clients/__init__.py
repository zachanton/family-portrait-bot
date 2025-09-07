# aiogram_bot_template/services/clients/__init__.py
from .factory import get_ai_client_and_model
from .local_ai_client import LocalAIClientResponse
from .fal_async_client import FalAsyncClient

__all__ = [
    "FalAsyncClient",
    "LocalAIClientResponse",
    "get_ai_client_and_model",
]

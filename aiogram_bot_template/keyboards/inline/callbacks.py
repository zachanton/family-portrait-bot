# aiogram_bot_template/keyboards/inline/callbacks.py
from aiogram.filters.callback_data import CallbackData

class LanguageCallback(CallbackData, prefix="lang"):
    action: str
    code: str

class FeedbackCallback(CallbackData, prefix="feedback"):
    action: str
    generation_id: int
    request_id: int
    continue_key: str

class RetryGenerationCallback(CallbackData, prefix="retry_gen"):
    """Callback to retry a request with a new seed."""
    request_id: int

class StyleCallback(CallbackData, prefix="style"):
    """Callback for selecting a generation style."""
    style_id: str
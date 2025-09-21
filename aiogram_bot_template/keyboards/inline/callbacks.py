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

class ContinueWithImageCallback(CallbackData, prefix="continue_with_img"):
    """Callback to proceed with a specific generated child image."""
    generation_id: int
    request_id: int

# --- NEW ---
class ContinueWithFamilyPhotoCallback(CallbackData, prefix="continue_with_family"):
    """Callback to proceed with a specific generated family photo."""
    generation_id: int
    request_id: int

class CreateFamilyPhotoCallback(CallbackData, prefix="create_family"):
    """Callback to start the family photo generation flow."""
    child_generation_id: int
    parent_request_id: int

class StyleCallback(CallbackData, prefix="style"):
    """Callback for selecting a generation style."""
    style_id: str

class ChildGenderCallback(CallbackData, prefix="child_gender"):
    gender: str

class ChildAgeCallback(CallbackData, prefix="child_age"):
    age: str

class ChildResemblanceCallback(CallbackData, prefix="child_resemblance"):
    resemblance: str
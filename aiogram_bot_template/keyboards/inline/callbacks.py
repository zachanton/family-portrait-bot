# aiogram_bot_template/keyboards/inline/callbacks.py
from aiogram.filters.callback_data import CallbackData


class Action(CallbackData, prefix="act"):
    action: str


class LanguageCallback(CallbackData, prefix="lang"):
    action: str
    code: str


class MainMenuCallback(CallbackData, prefix="menu"):
    action: str


class AgeSelectionCallback(CallbackData, prefix="child_age"):
    age_group: str


class GenderSelectionCallback(CallbackData, prefix="child_gender"):
    gender: str


class LikenessSelectionCallback(CallbackData, prefix="child_likeness"):
    resemble: str


class ContinueEditingCallback(CallbackData, prefix="cont_edit"):
    key: str


class GetHdCallback(CallbackData, prefix="get_hd"):
    key: str

class CreateGroupPhotoCallback(CallbackData, prefix="gp_create"):
    """Callback to initiate the group photo generation pipeline."""
    key: str


class RetryGenerationCallback(CallbackData, prefix="retry_gen"):
    """Callback to retry a request with a new seed."""
    request_id: int


class EditChildParamsCallback(CallbackData, prefix="edit_params"):
    """Callback to re-configure a request's parameters."""
    request_id: int


class ShowNextStepSubmenu(CallbackData, prefix="show_submenu"):
    """Callback to show a specific submenu for the next step."""
    menu: str
    request_id: int
    key: str


class ReturnToMainMenu(CallbackData, prefix="main_menu"):
    """Callback to return to the main next_step keyboard."""
    request_id: int
    key: str


class FeedbackCallback(CallbackData, prefix="feedback"):
    """Callback for providing feedback on a specific generation."""
    action: str
    generation_id: int
    request_id: int
    continue_key: str


class CancelPaymentCallback(CallbackData, prefix="cancel_pay"):
    generation_id: int  # Corresponds to request_id in this context


class BackToPromptSelection(CallbackData, prefix="back_prompt"):
    is_child_gen: bool | None = None


class EditMenuCallback(CallbackData, prefix="edit_menu"):
    """
    Callback for navigating the edit suggestions menu.
    'path' represents the keys to traverse the menu, separated by ':'.
    An empty path signifies the main menu.
    """
    path: str | None = None

class ReturnToGenerationCallback(CallbackData, prefix="return_gen"):
    """Callback to make a previous generation active again."""
    generation_id: int
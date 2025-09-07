# aiogram_bot_template/data/message_provider.py
from aiogram.utils.i18n import gettext as _

def get_start_message() -> str:
    """Returns the main welcome message for a new user."""
    return _(
        "<b>Welcome! Ready to see a glimpse of your future child? 😊</b>\n\n"
        "To begin, please send the first parent's photo.\n\n"
        "<i>(Tip: a clear, front-facing portrait works best!)</i>"
    )

def get_restart_message() -> str:
    """Returns the message for a user who restarts the bot."""
    return _(
        "Okay, let's start a new one. Your previous session has been reset.\n\n"
        "<b>Please send the first parent's photo.</b> 👤"
    )
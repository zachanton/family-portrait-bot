# aiogram_bot_template/states/user.py
from aiogram.fsm.state import State, StatesGroup


class Language(StatesGroup):
    selecting = State()


class Generation(StatesGroup):
    """A simplified flow for group photo generation."""

    collecting_photos = State()
    waiting_for_quality = State()
    waiting_for_payment = State()
    waiting_for_feedback = State()
    waiting_for_next_action = State()
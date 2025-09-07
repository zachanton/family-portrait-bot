# aiogram_bot_template/states/user.py
from aiogram.fsm.state import State, StatesGroup


class Language(StatesGroup):
    selecting = State()


class Generation(StatesGroup):
    """A single flow for all types of generations."""

    collecting_inputs = State()  # State for collecting photos

    # States specific to image_edit
    waiting_for_prompt = State()
    waiting_for_caption_confirm = State()
    waiting_for_user_prompt_confirm = State()
    waiting_for_quality = State()
    waiting_for_trial_confirm = State()

    # States specific to child_generation
    waiting_for_options = State()  # Waiting for selection (age, gender, etc.)

    # Common state
    waiting_for_payment = State()
    waiting_for_feedback = State()
    waiting_for_next_action = State()
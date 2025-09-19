# aiogram_bot_template/states/user.py
from aiogram.fsm.state import State, StatesGroup


class Language(StatesGroup):
    selecting = State()


# --- REFACTORED: Adapted for the new, more complex flow ---
class Generation(StatesGroup):
    """
    A full generation flow, starting with photo collection and
    branching into specific generation types.
    """
    collecting_photos = State()

    # --- States for child generation parameter selection ---
    choosing_child_gender = State()
    choosing_child_age = State()
    choosing_child_resemblance = State()

    # --- Common states for all pipelines ---
    waiting_for_quality = State()
    waiting_for_payment = State()
    waiting_for_feedback = State()
    waiting_for_next_action = State()
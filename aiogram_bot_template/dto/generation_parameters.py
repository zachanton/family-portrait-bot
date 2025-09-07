# File: aiogram_bot_template/dto/generation_parameters.py

from pydantic import BaseModel


class GenerationParameters(BaseModel):
    """
    A type-safe data transfer object for storing all user-configurable
    parameters for a generation request.
    """
    age_group: str | None = None
    gender: str | None = None
    resemble: str | None = None

    # This now holds the raw text from the user, whether from a button or free text.
    original_prompt_text: str | None = None

    # The prompt_for_enhancer field can hold the simplified instruction from buttons
    prompt_for_enhancer: str | None = None

    def to_db_json(self) -> str:
        """Serializes the model to a JSON string for database storage."""
        # exclude_none=True ensures that we don't save empty fields to the DB
        return self.model_dump_json(exclude_none=True)

    @classmethod
    def from_fsm_data(cls, fsm_data: dict) -> "GenerationParameters":
        """Factory method to safely create an instance from FSM state data."""
        return cls.model_validate(fsm_data, from_attributes=True)

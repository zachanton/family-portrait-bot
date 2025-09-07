# aiogram_bot_template/data/texts/dto.py
from pydantic import BaseModel
from typing import List


class BotCommandInfo(BaseModel):
    """Stores information for a single bot command."""
    command: str
    description: str


class BotInfo(BaseModel):
    """Stores the bot's description and short description."""
    description: str
    short_description: str


class LocaleTexts(BaseModel):
    """A collection of all texts for a specific locale."""
    privacy_policy: List[str]  # Changed to List[str]
    terms_of_service: List[str] # Changed to List[str]
    commands: List[BotCommandInfo]
    bot_info: BotInfo
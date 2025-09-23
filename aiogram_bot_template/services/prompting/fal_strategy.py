# aiogram_bot_template/services/prompting/fal_strategy.py
from typing import Dict, Any
from aiogram.utils.i18n import gettext as _
from pathlib import Path

from .base_strategy import PromptStrategy
# --- ChildGenerationHints is no longer needed here ---
from aiogram_bot_template.data.constants import ChildAge

from .styles import (
    PROMPT_RETRO_MOTEL,
    PROMPT_GOLDEN_HOUR,
    PROMPT_BAROQUE,
    PROMPT_OLD,
    PROMPT_PARTY_POLAROID,
    PROMPT_HOLLYWOOD_GLAMOUR,
    PROMPT_COLOR_GEL,
    PROMPT_VOGUE,
    PROMPT_WET_PLATE,
    PROMPT_POP_ART,
    PROMPT_GOLDEN_HOUR_NEXT_SHOT,

    PROMPT_CHILD_DEFAULT,
    PROMPT_FAMILY_DEFAULT
)

STYLE_PROMPTS = {
    "old": PROMPT_OLD,
    "party_polaroid": PROMPT_PARTY_POLAROID,
    "hollywood_glamour": PROMPT_HOLLYWOOD_GLAMOUR,
    "color_gel": PROMPT_COLOR_GEL,
    "vogue": PROMPT_VOGUE,
    "retro_motel": PROMPT_RETRO_MOTEL,
    "golden_hour": PROMPT_GOLDEN_HOUR,
    "baroque": PROMPT_BAROQUE,
    "wet_plate": PROMPT_WET_PLATE,
    "pop_art": PROMPT_POP_ART,
}

STYLE_PROMPTS_NEXT = {
    "golden_hour": PROMPT_GOLDEN_HOUR_NEXT_SHOT,
}

STYLE_DESCRIPTIONS = {
    "golden_hour": (
        "A romantic, warm, and natural photoshoot set in a sun-drenched field or on a serene coastline during the last hour before sunset. "
        "The aesthetic is soft, dreamy, and intimate. Wardrobe should be casual, comfortable, and timeless, made from natural fabrics. "
        "Think light linens, soft cottons, and flowing silhouettes in a palette of cream, beige, light earth tones, and muted pastels. "
        "Hair should be styled naturally, as if touched by a gentle breeze."
    ),
}


def get_translated_style_name(style: str) -> str:
    style_map = {
        "golden_hour": _("Golden Hour Backlit Portrait"),
    }
    return style_map.get(style, style.replace("_", " ").title())


class FalStrategy(PromptStrategy):
    """
    Prompt strategy for models like Fal.ai and Google Gemini.
    """

    def _get_child_prompt_template(
        self, age: str, gender: str, resemblance: str
    ) -> str:
        """
        Dynamically loads the correct prompt file based on the child's parameters.
        """
        try:
            age_name = ChildAge(age).name.lower()
        except ValueError:
            if age == "2": age_name = "infant"
            elif age == "7": age_name = "child"
            else: age_name = "teen"

        prompt_path = (
            Path(__file__).parent
            / "styles"
            / "child_generation"
            / age_name
            / gender
            / f"{resemblance}.txt"
        )
        if not prompt_path.exists():
            raise FileNotFoundError(f"Prompt file not found at: {prompt_path}")

        return prompt_path.read_text(encoding="utf-8")

    def create_group_photo_payload(self, style: str) -> Dict[str, Any]:
        prompt = STYLE_PROMPTS.get(style, PROMPT_GOLDEN_HOUR)
        return {"prompt": prompt, "temperature": 0.3}

    def create_group_photo_next_payload(self, style: str) -> Dict[str, Any]:
        prompt = STYLE_PROMPTS_NEXT.get(style, PROMPT_GOLDEN_HOUR_NEXT_SHOT)
        return {"prompt": prompt, "temperature": 0.5}
    
    def create_pair_photo_payload(self, style: str) -> Dict[str, Any]:
        prompt = STYLE_PROMPTS.get(style, PROMPT_GOLDEN_HOUR)
        return {"prompt": prompt, "temperature": 0.3}
    

    

    def create_family_photo_payload(self, style: str | None = None) -> Dict[str, Any]:
        prompt = PROMPT_FAMILY_DEFAULT
        return {"prompt": prompt, "temperature": 0.5}

    def create_child_generation_payload(
        self,
        child_gender: str,
        child_age: str,
        child_resemblance: str
    ) -> Dict[str, Any]:
        """
        Creates the payload for generating a child's portrait using a dynamically loaded prompt template.
        """
        prompt = PROMPT_CHILD_DEFAULT

        return {
            "prompt": prompt,
            "temperature": 0.3,
        }
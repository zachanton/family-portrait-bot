# aiogram_bot_template/services/prompting/fal_strategy.py
from typing import Dict, Any
from aiogram.utils.i18n import gettext as _

from .base_strategy import PromptStrategy
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
    PROMPT_GOLDEN_HOUR_NEXT_SHOT
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

# New dictionary for "next shot" prompts
STYLE_PROMPTS_NEXT = {
    "golden_hour": PROMPT_GOLDEN_HOUR_NEXT_SHOT,
    # ... (keep other styles as they are)
}

# --- NEW: Detailed style descriptions for the photoshoot planner ---
STYLE_DESCRIPTIONS = {
    "golden_hour": (
        "A romantic, warm, and natural photoshoot set in a sun-drenched field or on a serene coastline during the last hour before sunset. "
        "The aesthetic is soft, dreamy, and intimate. Wardrobe should be casual, comfortable, and timeless, made from natural fabrics. "
        "Think light linens, soft cottons, and flowing silhouettes in a palette of cream, beige, light earth tones, and muted pastels. "
        "Hair should be styled naturally, as if touched by a gentle breeze."
    ),
    # Add other styles here in the future
}


def get_translated_style_name(style: str) -> str:
    # This function is still useful for user-facing captions
    style_map = {
        "golden_hour": _("Golden Hour Backlit Portrait"),
        # ... (keep other styles)
    }
    return style_map.get(style, style.replace("_", " ").title())


class FalStrategy(PromptStrategy):
    """
    Prompt strategy for models like Fal.ai and Google Gemini.
    """
    def create_group_photo_payload(self, style: str) -> Dict[str, Any]:
        """
        Returns a detailed prompt and optimized parameters for generating a group portrait,
        based on the selected style.
        """
        prompt = STYLE_PROMPTS.get(style, PROMPT_GOLDEN_HOUR)
        
        return {
            "prompt": prompt,
            "temperature": 0.3,
        }

    def create_group_photo_next_payload(self, style: str) -> Dict[str, Any]:
        """
        Returns a detailed prompt and optimized parameters for generating the next shot
        in a group portrait sequence.
        """
        prompt = STYLE_PROMPTS_NEXT.get(style, PROMPT_GOLDEN_HOUR_NEXT_SHOT)
        
        return {
            "prompt": prompt,
            "temperature": 0.5,
        }

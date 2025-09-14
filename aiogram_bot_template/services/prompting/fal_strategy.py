# aiogram_bot_template/services/prompting/fal_strategy.py
from typing import Dict, Any
from aiogram.utils.i18n import gettext as _

from .base_strategy import PromptStrategy
from .styles import (
    PROMPT_DEFAULT, 
    PROMPT_RETRO_MOTEL, 
    PROMPT_GOLDEN_HOUR, 
    PROMPT_BAROQUE,
    PROMPT_OLD,
    PROMPT_PARTY_POLAROID,
    PROMPT_HOLLYWOOD_GLAMOUR,
    PROMPT_COLOR_GEL,
    PROMPT_VOGUE,
    PROMPT_WET_PLATE,
    PROMPT_POP_ART

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

def get_translated_style_name(style: str) -> str:
    """Returns a translatable, human-readable name for a given style key."""
    style_map = {
        "old": _("19th-century Studio Portrait"),
        "party_polaroid": _("Party Polaroid Portrait"),
        "hollywood_glamour": _("1930s Hollywood Glamour Portrait"),
        "color_gel": _("1980s Color-Gel Studio Portrait"),
        "vogue": _("Vogue High-Key Editorial Portrait"),
        "retro_motel": _("Retro Motel 1950s Pastel Portrait"),
        "golden_hour": _("Golden Hour Backlit Haze Portrait"),
        "baroque": _("Baroque Chiaroscuro Portrait"),
        "wet_plate": _("Wet-Plate Collodion Tonality Portrait"),
        "pop_art": _("Pop-Art Color Block Portrait"),

        
    }
    # Fallback for any new styles added that aren't in the map yet
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
        prompt = STYLE_PROMPTS.get(style, PROMPT_DEFAULT)
        
        # We return a more generic payload. `temperature` is used by Gemini,
        # while `guidance_scale` and `num_inference_steps` might be used by others like Fal.
        return {
            "prompt": prompt.replace('\n', ' '),
            "temperature": 0.3, # Good for creative but not chaotic results in Gemini
        }
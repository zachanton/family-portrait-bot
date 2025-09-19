# aiogram_bot_template/services/prompting/fal_strategy.py
from typing import Dict, Any
from aiogram.utils.i18n import gettext as _
from pathlib import Path

from .base_strategy import PromptStrategy
from aiogram_bot_template.services.child_feature_enhancer import ChildGenerationHints
# --- NEW: Import constants to map enum values to directory names ---
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
    PROMPT_GOLDEN_HOUR_NEXT_SHOT
)
# --- REMOVED: No longer importing a single child prompt ---
# from .styles import PROMPT_CHILD_GENERATION


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

    # --- NEW HELPER METHOD ---
    def _get_child_prompt_template(
        self, age: str, gender: str, resemblance: str
    ) -> str:
        """
        Dynamically loads the correct prompt file based on the child's parameters.

        Args:
            age: The age value from the ChildAge enum (e.g., "2", "7", "14").
            gender: The gender string (e.g., "boy", "girl").
            resemblance: The resemblance string (e.g., "mom", "dad", "both").

        Returns:
            The content of the corresponding prompt file.

        Raises:
            FileNotFoundError: If the prompt file for the combination does not exist.
        """
        # Map the age value (e.g., "2") to the directory name (e.g., "infant")
        try:
            age_name = ChildAge(age).name.lower()
        except ValueError:
            # Fallback for safety, though it should always be a valid enum value
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

    # --- MODIFIED METHOD ---
    def create_child_generation_payload(
        self,
        hints: ChildGenerationHints,
        child_gender: str,
        child_age: str,
        child_resemblance: str
    ) -> Dict[str, Any]:
        """
        Creates the payload for generating a child's portrait using enhanced hints
        and a dynamically loaded prompt template.
        """
        # Format hints into a readable block
        hints_text = (
            f"**Genetic Guidance:** {hints.genetic_guidance}\n"
            f"**Facial Structure Notes:** {hints.facial_structure_notes}\n"
            f"**Distinguishing Features:** {hints.distinguishing_features}"
        )

        # Dynamically load the correct prompt template
        prompt = self._get_child_prompt_template(
            age=child_age, gender=child_gender, resemblance=child_resemblance
        )

        # Replace placeholders in the loaded prompt
        prompt = prompt.replace("{{ENHANCED_HINTS_DATA}}", hints_text)
        prompt = prompt.replace("{{child_age}}", child_age)
        prompt = prompt.replace("{{child_gender}}", child_gender)
        prompt = prompt.replace("{{child_resemblance}}", child_resemblance)
        
        return {
            "prompt": prompt,
            "temperature": 0.4,
        }
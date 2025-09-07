# aiogram_bot_template/services/prompting/fal_strategy.py
from typing import Dict, Any
from .base_strategy import PromptStrategy

class FalStrategy(PromptStrategy):
    """
    Prompt strategy for models running on Fal.ai.
    """
    def create_group_photo_payload(self) -> Dict[str, Any]:
        """
        Returns a detailed prompt and optimized parameters for Fal.ai models.
        """
        prompt = (
            "Edit the two input photos into ONE cohesive, natural outdoor group portrait — not a collage. "
            "HARD IDENTITY LOCK — 100% FACE MATCH for both people: "
            "Reproduce the exact facial geometry and skin texture; preserve hairline and HAIR COLOR. "
            "No beautification, smoothing, or age changes. Expressions and poses may change slightly to fit the scene. "
            "Unify the lighting to a soft, golden-hour look. "
            "The background should be a softly blurred park. "
            "Output: photorealistic, vertical 4:5, 4K sRGB."
        )
        
        return {
            "prompt": " ".join(prompt.split()),
            "guidance_scale": 4.5,
            "num_inference_steps": 36,
            "output_format": "png",
        }
# aiogram_bot_template/services/prompting/fal_strategy.py
from typing import Dict, Any
from .base_strategy import PromptStrategy

from typing import Dict, Any
from .base_strategy import PromptStrategy

class FalStrategy(PromptStrategy):
    """
    Prompt strategy for models like Fal.ai and Google Gemini.
    """
    def create_group_photo_payload(self) -> Dict[str, Any]:
        """
        Returns a detailed prompt and optimized parameters for generating a group portrait.
        This prompt is designed to be robust for modern vision models.
        """
        prompt = (
            "Merge the two individuals from the provided pre-processed images into a single, cohesive, "
            "ultra-realistic group portrait. "
            "**Primary Goal: Absolute Identity Lock.** "
            "Crucially, preserve 100% of the facial features, identity, skin tone, hair color, and ethnicity of each person. "
            "Do not beautify, age, or alter their faces in any way. The resemblance must be perfect. "
            "**Scene & Composition:** "
            "Create a natural, warm, and relaxed couple's pose. They are standing close, smiling gently towards the camera. "
            "The interaction should feel genuine. "
            "**Background:** "
            "Place them in a beautiful, out-of-focus natural environment with a strong bokeh effect, like a lush green park during the golden hour. "
            "The background must not be distracting. "
            "**Lighting:** "
            "Use soft, warm, directional golden-hour lighting that unifies both people seamlessly into the scene. "
            "**Style & Quality:** "
            "The final image must be professional-grade, high-detail photorealism, as if taken with a high-quality 85mm f/1.4 portrait lens. "
            "The output should be a vertical 4:5 aspect ratio portrait. "
            "**Avoid:** "
            "A 'pasted' or 'collage' look, distorted features, unnatural skin textures, or mismatched lighting."
        )
        
        # We return a more generic payload. `temperature` is used by Gemini,
        # while `guidance_scale` and `num_inference_steps` might be used by others like Fal.
        return {
            "prompt": " ".join(prompt.replace("\n", " ").split()),
            "temperature": 0.8, # Good for creative but not chaotic results in Gemini
        }
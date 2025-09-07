# aiogram_bot_template/services/prompting/cloud/fal_strategy.py
from aiogram_bot_template.dto.facial_features import ImageDescription
from aiogram_bot_template.dto.llm_responses import (
    EmptyOutput, SinglePromptOutput, PromptWithControlParams
)
from aiogram_bot_template.services.prompting.common_base import (
    BasePromptStrategy
)
from aiogram_bot_template.dto.llm_responses import PromptBlueprint


class FalFluxStrategy(BasePromptStrategy):
    """
    Prompt strategy for FLUX.1 Kontext [pro] on Fal.ai.
    This strategy generates detailed blueprints where the Enhancer's role is to be a
    "geneticist", directly analyzing data and embedding specific features into the final prompt.
    """

    @staticmethod
    def _hard_inheritance_from_primary(primary_parent_str: str, hair_color: str) -> str:
        """
        Adult-identity traits only (no child-specific cues).
        """
        return (
            f"HARD — resemble the {primary_parent_str}: face shape and soft-tissue topology adapted to age; "
            "jawline contour and chin geometry; nose bridge width and tip shape; "
            "philtrum length and Cupid's bow; eyebrow arch and spacing; "
            f"eyelid and eye shape (not size); lightened {hair_color} hair color  and base texture."
        )

    def create_child_generation_blueprint(
        self, p1, p2, age: int, gender: str, resemble: str
    ) -> PromptBlueprint:
        # Identify parents by gender
        p1_gender = (getattr(p1, "gender", "") or "").lower()
        father = p1 if p1_gender == "male" else p2
        mother = p2 if father is p1 else p1

        # Pick resemblance driver
        primary_parent = father if (resemble or "").lower() == "father" else mother
        secondary_parent = mother if primary_parent is father else father
        primary_parent_str = "father" if primary_parent is father else "mother"
        secondary_parent_str = "mother" if primary_parent is father else "father"

        child_gender = (gender or "girl").lower()
        sp_iris_color = getattr(getattr(secondary_parent, "eyes", object()), "color", "blue")
        pm_hair_color = getattr(getattr(primary_parent, "hair", object()), "color", "blonde")

        hard_block = self._hard_inheritance_from_primary(primary_parent_str, pm_hair_color)

        # NSFW-safe, token-efficient prompt (mirrors the phrasing that worked for you)
        prompt = (
            f"Create a photorealistic head-and-shoulders portrait of a {age}-year-old {child_gender}. "
            f"Use the first reference image as the {primary_parent_str} (primary) and the last as the {secondary_parent_str} (secondary). "
            "The child must be a plausible biological offspring. "
            f"{hard_block} "
            "Do not beautify or adultify; keep true age-appropriate proportions. "
            "The portrait should include only the head and shoulders, without showing the chest. "
            f"Inheritance rules: iris color comes only from the {secondary_parent_str}: {sp_iris_color}. "
            "Expression & gaze: calm, open eyes, neutral brows, slight friendly smile. "
            "Styling & scene: plain white T-shirt; hair natural; no makeup; no earrings or jewelry. "
            "Background: neutral, slightly blurred outdoor greenery (soft nature bokeh) with soft diffused light. "
            "Output one high-resolution color image."
        )

        return PromptBlueprint(
            enhancer_bypass_payload={
                "prompt": " ".join(prompt.split()),
                "guidance_scale": 6.5,
                "num_inference_steps": 36,
                "output_format": "png",
            }
        )

    def create_image_edit_blueprint(self) -> PromptBlueprint:
        system_prompt = """You are an expert prompt engineer for the FLUX.1 model, which only accepts a positive prompt and control parameters. Your task is to convert a user's request into a structured JSON object.

**INSTRUCTIONS:**
1.  **Analyze Inputs**: Understand the user's intent from their text, the reference image, and its JSON description.
2.  **Construct Prompt**: Create a powerful prompt string for the edit. It must preserve the person's identity.
3.  **Embed Quality**: The prompt must include: "The final result must be photorealistic, with high-resolution details and clean textures."
4.  **Token Limit**: The 'prompt' string must be concise and under 512 tokens.
5.  **Determine Parameters**: Choose appropriate values for `guidance_scale` (e.g., 4.0) and `num_inference_steps` (e.g., 36).
6.  **Output Format**: Return a JSON object with "prompt", "guidance_scale", and "num_inference_steps".
"""
        return PromptBlueprint(
            system_prompt=" ".join(system_prompt.split()),
            output_model=PromptWithControlParams
        )
    
    def create_group_photo_blueprint(self) -> PromptBlueprint:
        prompt = (
    "Edit the three input photos into ONE cohesive, natural outdoor family portrait — not a collage. "
    "HARD IDENTITY LOCK — 100% FACE MATCH (for each person): "
    "Reproduce the exact facial geometry/spacing and the freckles/moles map with real skin texture; "
    "preserve hairline, hairstyle shape/direction and HAIR COLOR. No beautification, smoothing, age or "
    "eye-color changes. Expressions/poses may change. "
    "Unify capture: 85 mm eye-level portrait look. Golden-hour lighting with one soft key 30–45° "
    "camera-left, gentle sky fill and subtle rim. Single white balance and one shadow direction. "
    "Rebuild full necks/shoulders; correct head-to-torso ratios (reduce the child’s head scale "
    "by ~3–5% if needed). "
    "Integration (remove collage feel): Add natural contact/occlusion shadows under chins and where "
    "bodies/hands touch; add subtle color bounce from clothing. Match sharpness and depth of field "
    "(all eyes equally sharp; background smoothly blurred). Match grain/noise and micro-contrast. "
    "Remove edge halos around hair; keep flyaway hairs natural. Use identical round catchlights at "
    "~10 o’clock in each eye. "
    "Wardrobe/background: Coordinated casual outfits; softly blurred park background consistent with the light. "
    "Remove straps and distractions. Adjust framing to avoid cropped fingers at the bottom edge. "
    "Output: photorealistic, vertical 4:5, 4K sRGB. If any face deviates from its source, refine until it is an exact match."
)
        
        prompt = "Edit the three input photos into ONE cohesive, natural family portrait — not a collage.\n\nHARD IDENTITY LOCK — 100% FACE MATCH:\nReproduce each person’s face exactly as in their own photo: identical geometry/spacing, freckles/moles and skin texture; preserve hairline/hairstyle shape and HAIR COLOR. No beautification, smoothing, age or eye-color changes. Expressions/poses may change.\n\nUnify camera & light:\n85 mm eye-level portrait look. Relight to one golden-hour setup — soft key 30–45° camera-left with gentle sky fill and a subtle rim; single white balance and one shadow direction. Rebuild full necks/shoulders; correct head-to-torso scale.\n\nIntegration (remove collage feel):\nGenerate natural contact/occlusion shadows where bodies touch; add subtle color bounce between skin and clothing. Match sharpness and depth of field (all eyes equally sharp; background smoothly blurred). Match grain/noise and micro-contrast across subjects. Remove any cutout seams and edge halos; preserve flyaway hairs.\n\nWardrobe/background:\nCoordinated casual outfits; simple blurred park background consistent with the light. Remove straps and distractions.\n\nOutput: photorealistic, vertical 4:5, 4K sRGB. If any face deviates from its source, refine until it is an exact match."
        return PromptBlueprint(
            enhancer_bypass_payload={
                "prompt": " ".join(prompt.split()),
                "guidance_scale": 3.5,
                "num_inference_steps": 36,
                "output_format": "png",
            }
        )
    
    def create_group_photo_edit_blueprint(self) -> PromptBlueprint:
        """For now, group photo editing uses the same logic as single image editing."""
        return self.create_image_edit_blueprint()


class FalGeminiStrategy(BasePromptStrategy):
    """Prompt strategy for Google's Gemini family of models."""

    def create_child_generation_blueprint(
        self, p1: ImageDescription, p2: ImageDescription, age: int, gender: str, resemble: str
    ) -> PromptBlueprint:
        """
        The most forceful and detailed blueprint. It commands the AI to treat the task
        not as a creative interpretation, but as a direct transformation of the first image
        into a child, preserving all unique facial features and demanding a natural look.
        """
        system_prompt = f"""You are an expert AI prompt engineer. Your task is to create a non-negotiable, highly specific prompt for a photorealistic image generation model that understands image references.

**YOUR CRITICAL INSTRUCTIONS:**
1.  **Core Mandate**: The final image **MUST BE** a direct, photorealistic transformation of the person in the **first image** into a child. It is not a suggestion; it is a command.
2.  **Assemble the Prompt**: Create a single, powerful prompt paragraph with the following components in order:
    - **A.** Start with the basics: "A photorealistic portrait of a {age}-year-old {gender}."
    - **B.** Add the resemblance command. It must be phrased this way: "The portrait must be an **unmistakably authentic young version of the person in the first reference image**."
    - **C.** List the features to be preserved. This is the most important part. Add this sentence verbatim: "**All of their unique facial features—the precise shape of their eyes, nose, mouth, chin, and jawline, as well as their facial proportions and hair color—must be perfectly preserved** and simply rendered as a younger version."

**OUTPUT FORMAT:**
Return a single JSON object with the key "prompt" containing the final assembled prompt. Do not add any extra commentary.
"""
        return PromptBlueprint(
            system_prompt=" ".join(system_prompt.split()),
            output_model=SinglePromptOutput
        )

    def create_image_edit_blueprint(self) -> PromptBlueprint:
        system_prompt = """You are an expert prompt engineer for the Google Gemini model. Convert a user's edit request into a single, cohesive instruction.

**INSTRUCTIONS:**
1.  **Analyze Inputs**: Understand the user's intent.
2.  **Formulate Positive Instruction**: Create the main command for the edit.
3.  **Formulate Negative Concepts**: Identify what the AI should avoid.
4.  **Construct Final Prompt**: Combine them using the template: "{Positive Instruction}. IMPORTANT: Strictly avoid the following elements: {Negative Concepts}."
5.  **Output Format**: Return a single JSON object with the key "prompt".
"""
        return PromptBlueprint(
            system_prompt=" ".join(system_prompt.split()),
            output_model=SinglePromptOutput
        )
    
    def create_group_photo_blueprint(self) -> PromptBlueprint:
        prompt = (
            "Edit the THREE input photos into ONE photorealistic outdoor family portrait — NOT a collage.\nSource order: Image 1 = mother, Image 2 = father, Image 3 = child.\n\nSUBJECT COUNT = 3 (exactly): one adult female, one adult male, one girl.\nNo extra people or duplicates anywhere. No background bystanders, silhouettes, mirrors/reflections,\nposters/statues/photos of faces. If any extra face appears, remove it and fill with background.\n\nIDENTITY LOCK for all three:\n- Exact face geometry and freckles/moles with real skin texture.\n- Preserve hairline/hairstyle and hair color; keep glasses/headwear if present.\n- Keep original head poses (micro-alignment only). No beautification or face-slimming.\n- No changes to age, eye color, or skin tone. If a face deviates, refine until it matches.\n\nINTEGRATION (remove collage feel):\n- Rebuild necks/shoulders; correct head-to-torso scale (child −3–5% if needed).\n- Natural overlap and contact shadows; subtle color bounce from clothing.\n- Unified capture and light: 85 mm eye-level, golden-hour soft key ~30–45° camera-left + gentle sky fill,\n  ONE white balance and ONE shadow direction.\n- Match sharpness, micro-contrast and grain/noise; all eyes equally sharp; background softly blurred.\n- Remove edge halos; keep flyaway hairs natural; remove logos/distractions.\n\nOUTPUT: vertical 4:5, 4096 px (4K) sRGB. Return a single image."
        )
        return PromptBlueprint(
            enhancer_bypass_payload={
                "prompt": " ".join(prompt.split()),
                "output_format": "png",
            }
        )

    def create_group_photo_edit_blueprint(self) -> PromptBlueprint:
        """For now, group photo editing uses the same logic as single image editing."""
        return self.create_image_edit_blueprint()


class FalRecraftStrategy(BasePromptStrategy):
    """
    Specialized strategy for fal-ai/recraft. It does not use text prompts.
    """
    def create_upscale_blueprint(self) -> PromptBlueprint:
        """Recraft does not use text prompts, so the blueprint requests an empty object."""
        return PromptBlueprint(
            system_prompt="This model takes no text input. Output an empty JSON object.",
            output_model=EmptyOutput
        )
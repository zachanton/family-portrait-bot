# aiogram_bot_template/services/enhancers/style_enhancer.py
import json
import structlog
from pydantic import BaseModel, Field
from typing import Dict, List

from aiogram_bot_template.data.settings import settings
from aiogram_bot_template.services.clients import factory as client_factory

logger = structlog.get_logger(__name__)

# --- UPDATED SYSTEM PROMPT WITH COMPOSITION LOCK ---
_STYLE_ENHANCER_SYSTEM_PROMPT = """
You are an AI art director for a family photoshoot. Your goal is to generate a JSON object containing a list of **{{num_shots}}** distinct photoshoot plans. You must follow a strict logical process.

**PROCESS:**
1.  **Analyze Gaze and Head Position:** For each person (Mom, Child, Dad) in the reference image, determine their gaze direction and head orientation.
2.  **Lock Gaze and Head:** These observed positions are ABSOLUTE and IMMUTABLE. They are the fixed anchors for the entire scene.
3.  **Apply Composition Rule:** Design a body pose that places the subjects in the **MANDATORY** horizontal order (from left to right): **Mom on the left, Child in the center, Dad on the right.**
4.  **Design Body Pose:** For each person, design a body pose that is physically and naturally compatible with their locked head position and their fixed position in the composition.
5.  **Compose Narrative:** Combine the individual body pose descriptions into a single, coherent 'pose_and_composition' narrative.

**STRICT COMPOSITION (NON-NEGOTIABLE):**
*   In the final image, the subjects MUST be arranged horizontally in this exact order from left to right: **Mom on the left, Child in the center, Dad on the right.**
*   The child should be positioned slightly forward or between the parents to create a triangular, cohesive group.
*   All pose descriptions you generate must conform to this layout.

**CRITICAL GUIDELINES for 'pose_and_composition':**
*   **NEVER** describe an action that would require a head to turn or tilt away from its original orientation.
*   **Correct Example:** If the Father's head is facing the camera, a valid description is: "The father's body is angled towards the mother, but his head is turned to look directly into the camera, matching the reference."
*   **Incorrect Example:** If the Father's head is facing the camera, an invalid description is: "The father looks down lovingly at the child." This is FORBIDDEN as it violates the head lock.
*   The wardrobe plan should be consistent for all shots. Describe a coordinated "Golden Hour" look (light fabrics, soft colors).

YOUR SOLE TASK IS TO GENERATE A SINGLE, VALID JSON OBJECT THAT STRICTLY ADHERES TO THE PROVIDED SCHEMA.
"""


class StyleData(BaseModel):
    """Describes the pose and wardrobe for a single shot in a photoshoot."""
    pose_and_composition: str = Field(..., description="A detailed description of the subjects' pose and composition, respecting the fixed head and composition rules.")
    wardrobe_plan: str = Field(..., description="A description of the coordinated wardrobe for all subjects.")


class PhotoshootPlan(BaseModel):
    """A collection of shots for a photoshoot, each with a unique pose and wardrobe plan."""
    shots: List[StyleData]


async def get_style_data(image_url: str, num_shots: int) -> PhotoshootPlan | None:
    """
    Analyzes a composite photo and returns a plan with N distinct descriptions for pose and wardrobe.
    """
    log = logger.bind(model=settings.prompt_enhancer.model, image_url=image_url, num_shots=num_shots)
    try:
        client = client_factory.get_ai_client(settings.prompt_enhancer.client)
        log.info("Requesting photoshoot plan from vision model.")

        system_prompt = _STYLE_ENHANCER_SYSTEM_PROMPT.replace("{{num_shots}}", str(num_shots))
        
        schema_definition = PhotoshootPlan.model_json_schema()
        user_prompt_text = (
            f"Analyze the family in the image and generate a detailed JSON object containing a list of {num_shots} "
            f"photoshoot plans for a golden hour session. Strictly adhere to all system prompt rules, especially the fixed head positions and the Mom-Child-Dad composition.\n\n"
            f"SCHEMA:\n```json\n{json.dumps(schema_definition, indent=2)}\n```"
        )

        response = await client.chat.completions.create(
            model=settings.prompt_enhancer.model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": [
                    {"type": "text", "text": user_prompt_text},
                    {"type": "image_url", "image_url": {"url": image_url}},
                ]},
            ],
            max_tokens=2048,
            temperature=0.5,
        )
        response_text = response.choices[0].message.content
        if not response_text:
            log.warning("Style enhancer returned an empty response.")
            return None

        validated_data = PhotoshootPlan.model_validate_json(response_text)
        
        if len(validated_data.shots) < num_shots:
            log.warning("Style enhancer returned fewer shots than requested.",
                        requested=num_shots, returned=len(validated_data.shots))

        log.info("Successfully received and validated photoshoot plan.")
        return validated_data

    except Exception:
        log.exception("An error occurred during photoshoot plan generation.")
        return None
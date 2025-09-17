# aiogram_bot_template/services/prompt_enhancer.py

import json
import asyncio
import structlog
from pydantic import BaseModel, Field
from aiogram_bot_template.data.settings import settings
from aiogram_bot_template.services.clients import factory as client_factory
from aiogram_bot_template.services.prompting.enhancer_photoshoot_prompt import PROMPT_ENHANCER_PHOTOSHOOT_SYSTEM

logger = structlog.get_logger(__name__)

# --- MODELS for Photoshoot Planning ---

class WardrobeAndGrooming(BaseModel):
    """Describes a consistent wardrobe and grooming style for one person throughout the photoshoot."""
    # --- REMOVED: hair_style field is gone ---
    upper_body_outfit: str = Field(..., description="A detailed description of the TOP part of the outfit. E.g., 'Simple, cream-colored linen blouse with short sleeves', 'Casual, light-blue button-down shirt made of cotton'.")
    lower_body_outfit: str = Field(..., description="A detailed description of the BOTTOM part of the outfit. E.g., 'Flowing beige maxi skirt', 'Dark denim jeans'.")
    accessories: str = Field(..., description="Minimal accessories. E.g., 'Small pearl stud earrings', 'No visible accessories'.")

class PoseDetails(BaseModel):
    """Describes a specific pose and interaction for one shot."""
    shot_type: str = Field(..., description="Shot framing. VARY SIGNIFICANTLY. E.g., 'Medium Shot (waist up)', 'Cowboy Shot (mid-thigh up)', 'Full-Length Shot'.")
    pose_description: str = Field(..., description="A clear, actionable description of the couple's pose and interaction. E.g., 'Person A gently touches Person B's cheek, both smiling softly at the camera', 'Walking hand-in-hand, looking towards the camera'.")
    expression: str = Field(..., description="Overall mood and expression. E.g., 'Joyful and relaxed', 'Intimate and serene', 'Playful and energetic'.")

class PhotoshootPlan(BaseModel):
    """A complete, structured plan for an entire photoshoot session."""
    person_a_style: WardrobeAndGrooming
    person_b_style: WardrobeAndGrooming
    poses: list[PoseDetails] = Field(..., description="A list of diverse and creative poses for the entire photoshoot, one for each shot.")

# ... (get_photoshoot_plan function remains the same) ...
async def get_photoshoot_plan(
    image_url: str,
    style_context: str,
    shot_count: int,
) -> PhotoshootPlan | None:
    if not settings.prompt_enhancer.enabled:
        logger.debug("Prompt enhancer (photoshoot planner) is disabled in settings.")
        return None

    log = logger.bind(
        planner_model=settings.prompt_enhancer.model,
        image_url=image_url,
        style_context=style_context,
        shot_count=shot_count
    )

    try:
        client = client_factory.get_ai_client(settings.prompt_enhancer.client)
        log.info("Requesting structured photoshoot plan from vision model.")

        schema_definition = PhotoshootPlan.model_json_schema()
        system_prompt = PROMPT_ENHANCER_PHOTOSHOOT_SYSTEM.replace(
            "{{style_concept}}", style_context
        ).replace(
            "{{shot_count}}", str(shot_count)
        )

        user_prompt_text = (
            f"Analyze the couple in the image. The photoshoot style is '{style_context}' and we need {shot_count} total shots. "
            f"Generate a consistent wardrobe plan and a list of exactly {shot_count} diverse poses for all shots."
            f"\n\nSCHEMA:\n```json\n{json.dumps(schema_definition, indent=2)}\n```"
        )

        user_message_content = [
            {"type": "text", "text": user_prompt_text},
            {"type": "image_url", "image_url": {"url": image_url}},
        ]

        response = await client.chat.completions.create(
            model=settings.prompt_enhancer.model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message_content},
            ],
            max_tokens=4096,
            temperature=0.7,
        )

        response_text = response.choices[0].message.content
        if not response_text:
            log.warning("Photoshoot planner returned an empty response.")
            return None

        json_data = json.loads(response_text)
        validated_data = PhotoshootPlan.model_validate(json_data)

        if len(validated_data.poses) != shot_count:
            log.error("Planner returned incorrect number of poses.",
                      expected=shot_count, got=len(validated_data.poses))
            return None

        log.info("Successfully received and validated photoshoot plan.")
        return validated_data

    except Exception:
        log.exception("An error occurred during photoshoot plan generation.")
        return None


# --- MODIFIED: format_photoshoot_plan_for_prompt no longer includes hair ---
def format_photoshoot_plan_for_prompt(plan: PhotoshootPlan, body_part: str = "full") -> str:
    """
    Formats the wardrobe and grooming part of the plan for injection into a prompt.
    """
    pa_style = plan.person_a_style
    pb_style = plan.person_b_style
    
    lines = [
        "**PHOTOSHOOT PLAN - WARDROBE & GROOMING:**",
        "- **Person A (Left):**",
        f"  - Outfit (Top): {pa_style.upper_body_outfit}",
    ]
    if body_part == "full":
        lines.append(f"  - Outfit (Bottom): {pa_style.lower_body_outfit}")
    lines.extend([
        f"  - Accessories: {pa_style.accessories}",
        "- **Person B (Right):**",
        f"  - Outfit (Top): {pb_style.upper_body_outfit}",
    ])
    if body_part == "full":
        lines.append(f"  - Outfit (Bottom): {pb_style.lower_body_outfit}")
    lines.append(f"  - Accessories: {pb_style.accessories}")
    
    return "\n".join(lines)


def format_pose_for_prompt(pose: PoseDetails) -> str:
    """Formats a single pose from the plan for injection into a prompt."""
    lines = [
        "**POSE DIRECTIVE:**",
        f"- **Shot Type:** {pose.shot_type}.",
        f"- **Pose & Interaction:** {pose.pose_description}.",
        f"- **Expression & Mood:** {pose.expression}.",
    ]
    return "\n".join(lines)
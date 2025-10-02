# aiogram_bot_template/services/enhancers/family_prompt_enhancer.py
import json
import structlog
from typing import List, Optional, Set

from pydantic import BaseModel, Field, field_validator
from aiogram_bot_template.data.settings import settings
from aiogram_bot_template.services.clients import factory as client_factory
from aiogram_bot_template.services.pipelines import PROMPT_FAMILY_DEFAULT

logger = structlog.get_logger(__name__)

# --- Pydantic Models for Structured LLM Output ---

class PhotoshootShot(BaseModel):
    """Defines the variable elements for a single shot in a photoshoot plan."""
    pose_and_composition: str = Field(
        ...,
        description="30–90 words; bodies may angle, heads/gaze remain as in reference."
    )
    wardrobe_plan: str = Field(
        ...,
        description="45–90 words; per-shot wardrobe paragraph for Mom, Child, and Dad."
    )

    @field_validator("pose_and_composition")
    @classmethod
    def _pose_len(cls, v: str) -> str:
        if len(v.split()) < 30:
            raise ValueError("pose_and_composition too short; provide 30–90 words.")
        return v.strip()

    @field_validator("wardrobe_plan")
    @classmethod
    def _wardrobe_len(cls, v: str) -> str:
        wc = len(v.split())
        if wc < 45 or wc > 100:
            raise ValueError("wardrobe_plan must be a single 45–90 word paragraph.")
        txt = v.lower()
        if ("mom" not in txt) or ("child" not in txt) or ("dad" not in txt):
            raise ValueError("wardrobe_plan must mention Mom, Child, and Dad explicitly.")
        return v.strip()

class PhotoshootPlan(BaseModel):
    """A collection of shots for a photoshoot."""
    shots: List[PhotoshootShot]


# --- System Prompt for the LLM ---

_FAMILY_PHOTOSHOOT_SYSTEM_PROMPT = """
You are an AI art director for a golden-hour family photoshoot. Output JSON ONLY that matches the schema.

GOAL
Deliver diversified shots that keep identity intact and vary both POSE and WARDROBE across shots.
Heads/gaze/expression are locked to the references. Do not turn heads away from camera or change mouth openness/teeth visibility.

NON-NEGOTIABLE LOCKS
• Identity fidelity > pose > style (strict priority).
• Left→center→right order: MOM, CHILD, DAD. The child is slightly in front or between the parents.
• No new people, no hats or sunglasses, no props, no face/eye occlusions. Keep hairstyles and any earrings.

POSE DIVERSITY (choose different combos across shots; heads/gaze remain locked)
• Posture: standing; one parent slightly crouched; one parent seated; both parents seated with child standing; dad seated; mom seated.
• Depth/spacing: tight triangle; medium triangle; parents behind child; equal depth with child slightly advanced.
• Body angles (not heads): ±15–35° toward the child or toward each other.
• Hands: on child’s shoulders; arm around child’s waist; hands lightly clasped in front of child; parents’ near shoulders touching; dad’s forearm light contact along child’s arm.
• Camera distance: tight three-quarter; medium three-quarter; wider three-quarter (still portrait 3:2).
• Camera height: eye-level; slightly above; slightly below.
• Micro-motion: subtle breeze in hair; gentle weight shift; soft fabric drape.

WARDROBE DIVERSITY (must differ between shots, but stay cohesive for golden hour)
Keep a sunlit neutral + soft pastel palette overall (off-white, cream, ecru, oatmeal, sand, pale blue, dusty rose, sage, light gray). For **each shot**, write ONE paragraph of 45–90 words named `wardrobe_plan` that:
• Mentions Mom, Child, and Dad with specific but compact outfits (silhouette + color family + fabric type; optional footwear/jewelry).
• Varies at least three axes across shots (silhouettes, color accents, sleeve length/neckline, footwear).
• Uses natural summer fabrics (linen, cotton, chambray, seersucker, light knit). No logos, no bold prints, no hats or sunglasses.
• Style guide for wording: one cohesive paragraph; short clauses; “Mom — …; Child — …; Dad — …”. No bullet lists.

WRITING RULES
• `pose_and_composition` must be 30–90 words, photographic, and explicitly state left/center/right positions, depth, body angles (heads unchanged), hand placement, and camera distance/height.
• Each shot must include at least two pose diversity axes and produce a wardrobe paragraph different from other shots.
• Never contradict the locks.

Return ONLY valid JSON that conforms to the schema. No commentary and no extra keys.
"""


async def get_enhanced_family_prompts(
    composite_image_url: str, num_prompts: int
) -> Optional[List[str]]:
    """
    Generates a list of fully-formed, ready-to-use prompts for a family photo generation.

    This function performs a single call to a language model to get a structured photoshoot plan,
    then injects the details for each shot into a base prompt template.

    Args:
        composite_image_url: URL to the stacked image of parents and child.
        num_prompts: The number of unique prompts (photo variations) to generate.

    Returns:
        A list of complete prompt strings, or None on failure.
    """
    log = logger.bind(model=settings.text_enhancer.model, image_url=composite_image_url, num_prompts=num_prompts)
    try:
        # 1. Get the structured photoshoot plan from the LLM
        client = client_factory.get_ai_client(settings.text_enhancer.client)
        log.info("Requesting diversified photoshoot plan for family photo.")

        schema_definition = PhotoshootPlan.model_json_schema()
        user_prompt_text = (
            f"Generate exactly {num_prompts} diversified shots for a golden-hour meadow portrait. "
            f"Heads/gaze/expression are locked; order MOM-left, CHILD-center, DAD-right. "
            f"Return JSON ONLY matching the schema below.\n\n"
            f"SCHEMA:\n```json\n{json.dumps(schema_definition, indent=2)}\n```"
        )

        response = await client.chat.completions.create(
            model=settings.text_enhancer.model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _FAMILY_PHOTOSHOOT_SYSTEM_PROMPT},
                {"role": "user", "content": [
                    {"type": "text", "text": user_prompt_text},
                    {"type": "image_url", "image_url": {"url": composite_image_url}},
                ]},
            ],
            max_tokens=2048,
            temperature=0.8,
            top_p=0.9,
        )

        content = response.choices[0].message.content if response.choices else None
        if not content:
            log.warning("Family prompt enhancer returned an empty response.")
            return None

        plan = PhotoshootPlan.model_validate_json(content)

        # 2. Assemble the final prompts by injecting plan details into the base template
        completed_prompts = []
        for i in range(num_prompts):
            # If we need more prompts than the plan has shots, cycle through the plan
            shot = plan.shots[i % len(plan.shots)]

            final_prompt = PROMPT_FAMILY_DEFAULT
            final_prompt = final_prompt.replace("{{POSE_AND_COMPOSITION_DATA}}", shot.pose_and_composition.strip())
            final_prompt = final_prompt.replace("{{PHOTOS_PLAN_DATA}}", shot.wardrobe_plan.strip())
            completed_prompts.append(final_prompt)

        log.info("Successfully generated enhanced family prompts.", count=len(completed_prompts))
        return completed_prompts

    except Exception:
        log.exception("An error occurred during family prompt enhancement.")
        return None
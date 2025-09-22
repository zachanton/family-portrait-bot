# aiogram_bot_template/services/enhancers/style_enhancer.py
import json
import structlog
from typing import List, Optional, Tuple, Set

from pydantic import BaseModel, Field, field_validator
from aiogram_bot_template.data.settings import settings
from aiogram_bot_template.services.clients import factory as client_factory

logger = structlog.get_logger(__name__)

# =========================
# System Prompt (classic format, richer wardrobe)
# =========================
_STYLE_ENHANCER_SYSTEM_PROMPT = """
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

# =========================
# Schema (classic format)
# =========================
class StyleData(BaseModel):
    pose_and_composition: str = Field(
        ...,
        description="30–90 words; bodies may angle, heads/gaze remain as in reference."
    )
    wardrobe_plan: str = Field(
        ...,
        description="45–90 words; per-shot wardrobe paragraph for Mom, Child, Dad."
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
        # minimal per-person mention check
        txt = v.lower()
        if ("mom" not in txt) or ("child" not in txt) or ("dad" not in txt):
            raise ValueError("wardrobe_plan must mention Mom, Child, and Dad explicitly.")
        return v.strip()

class PhotoshootPlan(BaseModel):
    shots: List[StyleData]

# =========================
# Public API
# =========================
async def get_style_data(image_url: str, num_shots: int) -> Optional[PhotoshootPlan]:
    """
    Analyze the family image and return N diversified shots with pose and richer wardrobe_plan paragraphs.
    """
    log = logger.bind(model=settings.prompt_enhancer.model, image_url=image_url, num_shots=num_shots)
    try:
        client = client_factory.get_ai_client(settings.prompt_enhancer.client)
        log.info("Requesting diversified photoshoot plan (classic format).")

        schema_definition = PhotoshootPlan.model_json_schema()
        user_prompt_text = (
            f"Generate exactly {num_shots} diversified shots for a golden-hour meadow portrait. "
            f"Heads/gaze/expression are locked; order MOM-left, CHILD-center, DAD-right. "
            f"Return JSON ONLY matching the schema below.\n\n"
            f"SCHEMA:\n```json\n{json.dumps(schema_definition, indent=2)}\n```"
        )

        response = await client.chat.completions.create(
            model=settings.prompt_enhancer.model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _STYLE_ENHANCER_SYSTEM_PROMPT},
                {"role": "user", "content": [
                    {"type": "text", "text": user_prompt_text},
                    {"type": "image_url", "image_url": {"url": image_url}},
                ]},
            ],
            max_tokens=2048,
            temperature=0.8,   # promotes wardrobe variety; locks keep identity safe
            top_p=0.9,
        )

        content = response.choices[0].message.content if response.choices else None
        if not content:
            log.warning("Style enhancer returned an empty response.")
            return None

        plan = PhotoshootPlan.model_validate_json(content)

        # Light duplicate guard: warn if wardrobe paragraphs are identical (case/spacing-insensitive)
        seen_norm: Set[str] = set()
        for idx, shot in enumerate(plan.shots):
            norm = " ".join(shot.wardrobe_plan.lower().split())
            if norm in seen_norm:
                logger.warning("Duplicate wardrobe_plan detected across shots.", index=idx)
            seen_norm.add(norm)

        log.info("Successfully received diversified photoshoot plan.")
        return plan

    except Exception:
        log.exception("An error occurred during photoshoot plan generation.")
        return None

# =========================
# Helper for master prompt
# =========================
def format_shot_for_prompt(shot: StyleData):
    """
    Returns a dict ready to inject into the master prompt placeholders.
    """
    return {
        "POSE_AND_COMPOSITION_DATA": shot.pose_and_composition.strip(),
        "PHOTOS_PLAN_DATA": shot.wardrobe_plan.strip(),
    }

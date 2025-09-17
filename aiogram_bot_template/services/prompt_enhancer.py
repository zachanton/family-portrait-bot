# aiogram_bot_template/services/prompt_enhancer.py

import json
import asyncio
import structlog
from pydantic import BaseModel, Field
from aiogram_bot_template.data.settings import settings
from aiogram_bot_template.services.clients import factory as client_factory
from aiogram_bot_template.services.prompting.enhancer_prompt import PROMPT_ENHANCER_SYSTEM
from aiogram_bot_template.services.prompting.enhancer_photoshoot_prompt import PROMPT_ENHANCER_PHOTOSHOOT_SYSTEM
from aiogram_bot_template.services.google_sheets_logger import GoogleSheetsLogger

logger = structlog.get_logger(__name__)


class EyesDetail(BaseModel):
    color: str
    shape: str

class NoseDetail(BaseModel):
    bridge: str
    tip: str
    nostrils: str

class IdentityLock(BaseModel):
    overall_impression: str
    face_geometry: str
    eyes: EyesDetail
    eyebrows: str
    nose: NoseDetail
    lips: str
    skin: str
    hair: str
    unique_details: str

class CleanupInstructions(BaseModel):
    artifacts: str
    seam: str
    logos: str

class EnhancedPromptData(BaseModel):
    person_a: IdentityLock
    person_b: IdentityLock
    cleanup: CleanupInstructions

class CameraDetails(BaseModel):
    shot_type: str = Field(..., description="Shot type. VARY SIGNIFICANTLY between shots. Examples: 'Extreme Close-Up', 'Close-Up', 'Medium Shot', 'Cowboy Shot (mid-thigh up)', 'Full-Length Shot'.")
    angle: str = Field(..., description="Camera angle. VARY between shots. Examples: 'Eye-level', 'Slight high angle', 'Slight low angle', 'Dutch angle'.")

class PoseDetails(BaseModel):
    expression: str = Field(..., description="A command for the subject's facial expression and where they are looking. E.g., 'Laughing, looking at Person B', 'Soft smile, looking at camera'.")
    head_tilt: str = Field(..., description="A command for the subject's head orientation. E.g., 'Slightly tilted left', 'Tilted back laughing', 'No tilt'.")
    body_posture: str = Field(..., description="A command for the subject's body posture and interaction. E.g., 'Leaning against Person A', 'Walking towards camera', 'Sitting on a bench, arm around Person B'.")

class CompositionDetails(BaseModel):
    framing: str = Field(..., description="A command describing the composition and subject placement. Use principles like 'Rule of Thirds', 'Leading Lines', 'Asymmetrical balance'. E.g., 'Subjects framed on the left third of the image', 'Centered subjects with negative space above'.")
    focus: str = Field(..., description="A command for the focus point and depth of field. E.g., 'Sharp focus on both subjects, background heavily blurred', 'Focus on Person A, Person B slightly soft'.")

class NextFrameData(BaseModel):
    narrative_link: str = Field(..., description="A brief command describing the emotional transition from the last shot. E.g., 'From a quiet glance to a shared laugh', 'From playful energy to a calm, loving embrace'.")
    camera: CameraDetails
    person_a_pose: PoseDetails
    person_b_pose: PoseDetails
    composition: CompositionDetails


def format_enhanced_data_as_text(data: EnhancedPromptData) -> str:
    """
    Formats the structured identity data into a directive block that downstream image models follow reliably.
    """
    def format_identity_lock(person_data, title):
        lines = [
            f"**{title}**",
            f"  - Essence: Capture their {person_data.overall_impression}.",
            f"  - Face Shape: Faithfully reproduce the subject's {person_data.face_geometry}.",
            f"  - Eyes: {person_data.eyes.shape} with a {person_data.eyes.color} color.",
            f"  - Eyebrows: {person_data.eyebrows}.",
            f"  - Nose Structure: '{person_data.nose.bridge}' bridge, '{person_data.nose.tip}' tip, '{person_data.nose.nostrils}' nostrils.",
            f"  - Mouth: {person_data.lips}.",
            f"  - Skin: {person_data.skin} (preserve pores; no beauty-smoothing).",
            f"  - Hair: {person_data.hair}.",
            f"  - Distinctive Features: {person_data.unique_details.replace('chest hair', 'subtle hair on the upper torso')}.",
        ]
        return "\n".join(lines)

    person_a_text = format_identity_lock(data.person_a, "LIKENESS GUIDELINES (PERSON A — LEFT)")
    person_b_text = format_identity_lock(data.person_b, "LIKENESS GUIDELINES (PERSON B — RIGHT)")

    cleanup_text = "\n".join([
        "**IMAGE CLEANUP**",
        f"  - Artifacts: {data.cleanup.artifacts}",
        f"  - Seam: {data.cleanup.seam}",
        f"  - Logos: {data.cleanup.logos}",
    ])

    artistic_hierarchy = (
        "**ARTISTIC HIERARCHY:** 1) Identity match is the highest priority. "
        "2) The likeness guidelines above are authoritative. "
        "3) Apply style (lighting, mood, wardrobe) without compromising identity."
    )

    constraints = (
        "**KEY CONSTRAINTS:** Maintain original facial proportions, expressions, age cues, and natural skin texture. Avoid idealized or generic features."
    )

    return (
        "IDENTITY LOCK — USE THIS OVER ALL OTHER CUES\n"
        + person_a_text + "\n\n" + person_b_text + "\n\n"
        + cleanup_text + "\n\n" + artistic_hierarchy + "\n" + constraints
    )


def format_next_frame_data_as_text(data: NextFrameData) -> str:
    """
    Formats the photoshoot 'next shot' plan into a compact, command-oriented block
    with built-in non-repeat rules and camera geometry guidance.
    """
    pa, pb = data.person_a_pose, data.person_b_pose

    shot_type = data.camera.shot_type.lower()
    if 'full-length' in shot_type or 'wide shot' in shot_type:
        crop_instruction = "CROP: Full-Length Shot. The entire body of both subjects must be visible within the 4:5 frame."
    elif 'cowboy' in shot_type:
        crop_instruction = "CROP: Cowboy Shot (mid-thigh up). Frame subjects from the mid-thigh up."
    elif 'medium' in shot_type or 'waist-up' in shot_type:
        crop_instruction = "CROP: Waist-Up Medium Shot. Frame subjects from the waist up."
    else:
        crop_instruction = "CROP: Head-and-shoulders crop as specified (Close-Up or Extreme Close-Up)."

    lines = [
        f"**NEXT SHOT DIRECTIVE:** {data.narrative_link}",
        "NON-REPEAT RULES: enforce a clearly different composition than the last shot — apply at least two: side swap; head-height stagger ≥3% of H; camera yaw offset ≥10°; changed air gap (state cm); changed overlap (%); crop change (e.g., waist-up).",
        f"  - Camera: {data.camera.shot_type}; angle: {data.camera.angle}.",
        f"  - Composition / Framing: {data.composition.framing}.",
        f"  - Focus / DoF: {data.composition.focus}.",
        f"  - Person A (Left): expression '{pa.expression}'; head tilt '{pa.head_tilt}'; posture '{pa.body_posture}'.",
        f"  - Person B (Right): expression '{pb.expression}'; head tilt '{pb.head_tilt}'; posture '{pb.body_posture}'.",
        "COORDINATE COMPLIANCE: if positions are specified as (x, y) in pixels for a 1536×1920 canvas or as normalized [0..1], obey strictly.",
        f"**{crop_instruction}**",
        "**FAILSAFE:** If the generated pose is too similar to the reference (e.g., subjects' eye centers within ±5% of previous positions, camera angle is straight-on), you MUST re-render with significant changes: increase camera yaw by at least 15°, add a ±5° roll, and widen the air gap between subjects' heads by at least 6 cm (unless an embrace is specified).",
    ]
    return "\n".join(lines)


async def get_enhanced_prompt_data(image_url: str) -> EnhancedPromptData | None:
    # This function remains the same
    if not settings.prompt_enhancer.enabled:
        logger.debug("Prompt enhancer is disabled in settings.")
        return None

    if not image_url:
        logger.warning("Cannot enhance prompt, image_url is missing.")
        return None

    log = logger.bind(
        enhancer_model=settings.prompt_enhancer.model,
        image_url=image_url,
    )

    try:
        client = client_factory.get_ai_client(settings.prompt_enhancer.client)
        
        log.info("Requesting structured prompt data from vision model.")
        
        schema_definition = EnhancedPromptData.model_json_schema()

        user_message_content = [
            {
                "type": "text",
                "text": f"Analyze the provided image and generate a JSON object that strictly adheres to the following schema. The field descriptions in the schema are part of your instructions.\n\nSCHEMA:\n```json\n{json.dumps(schema_definition, indent=2)}\n```",
            },
            {
                "type": "image_url",
                "image_url": {"url": image_url},
            },
        ]

        response = await client.chat.completions.create(
            model=settings.prompt_enhancer.model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": PROMPT_ENHANCER_SYSTEM},
                {"role": "user", "content": user_message_content},
            ],
            max_tokens=4096,
            temperature=0.1,
        )

        response_text = response.choices[0].message.content
        
        log.info(
            "Received raw response from identity lock enhancer.", 
            raw_enhancer_response=response_text
        )
        
        if not response_text:
            log.warning("Prompt enhancer returned an empty response.")
            return None
        
        try:
            json_data = json.loads(response_text)
            validated_data = EnhancedPromptData.model_validate(json_data)
            
            log.info(
                "Successfully received and validated structured prompt data.",
            )

            asyncio.create_task(
                GoogleSheetsLogger().log_prompt_enhancement(
                    user_content=user_message_content,
                    system_prompt=PROMPT_ENHANCER_SYSTEM,
                    model_name=settings.prompt_enhancer.model,
                    result_model=validated_data
                )
            )

            return validated_data
        except (json.JSONDecodeError, Exception) as e:
            log.exception(
                "Failed to parse or validate JSON from enhancer model.",
                response_text=response_text,
                error=str(e)
            )
            return None

    except Exception:
        log.exception("An error occurred during prompt enhancement call.")
        return None

async def get_next_frame_data(
    image_url: str, 
    style_context: str
) -> NextFrameData | None:
    """
    Calls a vision model to get structured commands for the next frame in a photoshoot.
    """
    if not settings.prompt_enhancer.enabled:
        logger.debug("Prompt enhancer is disabled in settings.")
        return None
    
    log = logger.bind(
        enhancer_model=settings.prompt_enhancer.model,
        image_url=image_url,
        style_context=style_context
    )
    
    try:
        client = client_factory.get_ai_client(settings.prompt_enhancer.client)
        log.info("Requesting structured data for the next photoshoot frame.")
        
        schema_definition = NextFrameData.model_json_schema()

        user_prompt_text = (
            f"This is the last shot. The overall style is '{style_context}'.\n"
            f"**CRITICAL:** Your new JSON response MUST describe a pose and composition that is different from the one in the image.\n\n"
            f"Generate JSON for the next shot according to the system prompt and this schema.\n\n"
            f"SCHEMA:\n```json\n{json.dumps(schema_definition, indent=2)}\n```"
        )

        user_message_content = [
            {"type": "text", "text": user_prompt_text},
            {"type": "image_url", "image_url": {"url": image_url}},
        ]

        response = await client.chat.completions.create(
            model=settings.prompt_enhancer.model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": PROMPT_ENHANCER_PHOTOSHOOT_SYSTEM},
                {"role": "user", "content": user_message_content},
            ],
            max_tokens=2048,
            temperature=0.8,
        )
        
        response_text = response.choices[0].message.content

        log.info(
            "Received raw response from photoshoot frame enhancer.",
            raw_enhancer_response=response_text
        )

        if not response_text:
            log.warning("Photoshoot enhancer returned an empty response.")
            return None

        try:
            json_data = json.loads(response_text)
            validated_data = NextFrameData.model_validate(json_data)
            log.info("Successfully validated next frame data.")
            return validated_data
        except (json.JSONDecodeError, Exception) as e:
            log.exception("Failed to parse or validate JSON for next frame data.", response_text=response_text, error=str(e))
            return None

    except Exception:
        log.exception("An error occurred during next frame data call.")
        return None
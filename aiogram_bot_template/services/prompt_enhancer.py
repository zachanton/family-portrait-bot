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


# ... (Все Pydantic модели остаются без изменений) ...
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
    shot_type: str = Field(..., description="E.g., 'Medium Close-Up', 'Close-Up', 'Extreme Close-Up'.")
    angle: str = Field(..., description="E.g., 'Eye-level', 'Slightly high angle', 'Slightly low angle'.")

class PoseDetails(BaseModel):
    expression: str = Field(..., description="A command for the subject's facial expression.")
    head_tilt: str = Field(..., description="A command for the subject's head orientation.")
    body_posture: str = Field(..., description="A command for the subject's body posture relative to the camera and the other person.")

class CompositionDetails(BaseModel):
    framing: str = Field(..., description="A command describing how to frame the subjects.")
    focus: str = Field(..., description="A command for the focus point and depth of field.")

class NextFrameData(BaseModel):
    narrative_link: str = Field(..., description="A brief command describing the emotional transition from the last shot.")
    camera: CameraDetails
    person_a_pose: PoseDetails
    person_b_pose: PoseDetails
    composition: CompositionDetails


def format_enhanced_data_as_text(data: EnhancedPromptData) -> str:
    """
    Formats the structured data into a detailed, safety-compliant, and syntactically correct text block.
    """
    def format_identity_lock(person_data, title):
        # The Python code now constructs the full, grammatically correct command.
        lines = [
            f"**{title}**",
            f"  - Essence: Capture their {person_data.overall_impression}.",
            f"  - Face Shape: Faithfully reproduce the subject's {person_data.face_geometry}.",
            f"  - Eyes: Render eyes that are {person_data.eyes.shape} with a {person_data.eyes.color} color.",
            f"  - Eyebrows: Draw eyebrows as {person_data.eyebrows}.",
            f"  - Nose Structure: Create a nose with a '{person_data.nose.bridge}' bridge, '{person_data.nose.tip}' tip, and '{person_data.nose.nostrils}' nostrils.",
            f"  - Mouth: The mouth and lips should be rendered as {person_data.lips}.",
            f"  - Skin: Render skin with {person_data.skin} and its natural texture.",
            f"  - Hair: The hair should be styled as {person_data.hair}.",
            f"  - Distinctive Features: Accurately include these details: {person_data.unique_details.replace('chest hair', 'subtle hair on the upper torso')}.",
        ]
        return "\n".join(lines)

    person_a_text = format_identity_lock(data.person_a, "LIKENESS GUIDELINES (PERSON A - LEFT)")
    person_b_text = format_identity_lock(data.person_b, "LIKENESS GUIDELINES (PERSON B - RIGHT)")
    
    cleanup_text = "\n".join([
        "**IMAGE CLEANUP**",
        f"  - Artifacts: {data.cleanup.artifacts}",
        f"  - Seam: {data.cleanup.seam}",
        f"  - Logos: {data.cleanup.logos}",
    ])

    artistic_hierarchy = (
        "**ARTISTIC HIERARCHY:** 1. Facial likeness from the reference photo is the highest priority. 2. The LIKENESS GUIDELINES above provide the necessary details for achieving it. 3. The overall style (lighting, mood, wardrobe) should be applied beautifully *without* compromising the facial likeness."
    )

    constraints = (
        "**KEY CONSTRAINTS:** Maintain the original facial proportions, expressions, age, and natural skin texture. Avoid generic or idealized features."
    )

    return f"{person_a_text}\n\n{person_b_text}\n\n{cleanup_text}\n\n{artistic_hierarchy}\n{constraints}"


def format_next_frame_data_as_text(data: NextFrameData) -> str:
    """
    Formats the structured photoshoot data into a compact, command-oriented text block.
    """
    person_a = data.person_a_pose
    person_b = data.person_b_pose
    
    lines = [
        f"**NEXT SHOT DIRECTIVE:** {data.narrative_link}",
        f"  - Camera: Use a {data.camera.shot_type} from a {data.camera.angle}. Frame the shot as follows: {data.composition.framing}. Focus on: {data.composition.focus}.",
        f"  - Person A (Left): Guide their expression to be '{person_a.expression}', with head tilt '{person_a.head_tilt}' and posture '{person_a.body_posture}'.",
        f"  - Person B (Right): Guide their expression to be '{person_b.expression}', with head tilt '{person_b.head_tilt}' and posture '{person_b.body_posture}'.",
    ]
    return "\n".join(lines)


# --- API call functions (existing and new) ---

async def get_enhanced_prompt_data(image_url: str) -> EnhancedPromptData | None:
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
        
        # --- MODIFICATION: Log the raw response immediately after receiving it ---
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
                # No need to log the validated data again, as the raw log contains everything.
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

async def get_next_frame_data(image_url: str, style_context: str) -> NextFrameData | None:
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

        user_message_content = [
            {
                "type": "text",
                "text": f"This is the last shot. The overall style is '{style_context}'. Generate JSON for the next shot according to the system prompt and this schema.\n\nSCHEMA:\n```json\n{json.dumps(schema_definition, indent=2)}\n```",
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
                {"role": "system", "content": PROMPT_ENHANCER_PHOTOSHOOT_SYSTEM},
                {"role": "user", "content": user_message_content},
            ],
            max_tokens=2048,
            temperature=0.4, # A bit more creative for poses
        )
        
        response_text = response.choices[0].message.content

        # --- MODIFICATION: Log the raw response immediately after receiving it ---
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
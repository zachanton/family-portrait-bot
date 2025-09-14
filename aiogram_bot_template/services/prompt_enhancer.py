# aiogram_bot_template/services/prompt_enhancer.py

import json
import asyncio
import structlog
from pydantic import BaseModel, Field
from aiogram_bot_template.data.settings import settings
from aiogram_bot_template.services.clients import factory as client_factory
from aiogram_bot_template.services.prompting.enhancer_prompt import PROMPT_ENHANCER_SYSTEM
from aiogram_bot_template.services.google_sheets_logger import GoogleSheetsLogger

logger = structlog.get_logger(__name__)


# --- Simplified Pydantic models focused on generating commands ---
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

def format_enhanced_data_as_text(data: EnhancedPromptData) -> str:
    """
    Formats the structured data into a compact, command-oriented text block
    for the final image generation model.
    """
    
    def format_identity_lock(person_data, title):
        # Format the nose details into a clean sub-list
        nose_text = (f"  *   **Bridge:** {person_data.nose.bridge}\n"
                     f"  *   **Tip:** {person_data.nose.tip}\n"
                     f"  *   **Nostrils:** {person_data.nose.nostrils}")

        lines = [
            f"**{title}**",
            f"*   **Essence & Expression:** {person_data.overall_impression}",
            f"*   **Facial Structure:** {person_data.face_geometry}",
            f"*   **Eyes:** {person_data.eyes.shape} | **Color:** {person_data.eyes.color}",
            f"*   **Eyebrows:** {person_data.eyebrows}",
            f"*   **Nose Forensic-Analysis:**\n{nose_text}",
            f"*   **Mouth & Smile:** {person_data.lips}",
            f"*   **Skin Details:** {person_data.skin}",
            f"*   **Hair:** {person_data.hair}",
            f"*   **Unique Details:** {person_data.unique_details}",
        ]
        return "\n".join(lines)

    # --- BUG FIX: Use neutral 'left'/'right' instead of hardcoded gender ---
    person_a_text = format_identity_lock(
        data.person_a, "IDENTITY LOCK — PERSON ON THE LEFT"
    )
    person_b_text = format_identity_lock(
        data.person_b, "IDENTITY LOCK — PERSON ON THE RIGHT"
    )
    
    cleanup_text = "\n".join([
        "**SOURCE-SPECIFIC CLEANUP**",
        f"*   {data.cleanup.artifacts}",
        f"*   {data.cleanup.seam}",
        f"*   {data.cleanup.logos}",
    ])

    meta_instruction = (
        "**--- META-INSTRUCTION: HIERARCHY OF CONTROL ---**\n"
        "1.  **IMAGE DATA IS LAW:** The provided reference image's pixel data for faces is the non-negotiable ground truth. Your primary function is to replicate it.\n"
        "2.  **IDENTITY LOCK IS THE COMMAND LIST:** The text descriptions above are a forensic command list, not creative suggestions. They clarify what to copy from the image data.\n"
        "3.  **STYLE IS APPLIED LAST:** All stylistic goals (lighting, wardrobe, etc.) must be applied *AROUND* the perfectly preserved facial identity. IDENTITY ALWAYS WINS."
    )

    negative_prompt = (
        "**--- NEGATIVE PROMPT: IDENTITY PRESERVATION FAILURES TO AVOID ---**\n"
        "*   **DO NOT** alter facial proportions (slimming faces, changing jawlines).\n"
        "*   **DO NOT** replace the subjects' unique expressions with generic 'photo smiles'.\n"
        "*   **DO NOT** age or de-age the subjects.\n"
        "*   **DO NOT** smooth or airbrush skin beyond what is present in the source. Replicate all real skin texture.\n"
        "*   **DO NOT** change the fundamental structure of the nose, eyes, or mouth."
    )

    return f"{person_a_text}\n\n{person_b_text}\n\n{cleanup_text}\n\n{meta_instruction}\n\n{negative_prompt}"

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
        if not response_text:
            log.warning("Prompt enhancer returned an empty response.")
            return None
        
        try:
            json_data = json.loads(response_text)
            validated_data = EnhancedPromptData.model_validate(json_data)
            
            log.info(
                "Successfully received and validated structured prompt data.",
                enhancer_result=validated_data.model_dump()
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
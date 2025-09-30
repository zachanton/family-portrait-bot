# aiogram_bot_template/services/enhancers/parent_visual_enhancer.py
import structlog
import numpy as np
from typing import Optional, List

from aiogram_bot_template.data.settings import settings
from aiogram_bot_template.services import similarity_scorer, photo_processing
from aiogram_bot_template.services.clients import factory as client_factory

logger = structlog.get_logger(__name__)

# --- NEW: System prompt for the Textual Feature Extractor ---
_TEXTUAL_ENHANCEMENT_SYSTEM_PROMPT = """
You are an expert AI photo analyst. Your mission is to distill the unique, permanent facial characteristics from a 2x2 photo collage into a concise descriptive paragraph. This description will guide a visual AI to recreate the person with maximum fidelity.

**Core Directives:**
1.  **Evidence-Based Analysis:** Your description must be grounded **exclusively** in the visual evidence from the collage. Do not invent, infer, or 'beautify' features.
2.  **Synthesize a Consensus:** Analyze all four tiles to form a consensus. If features vary (e.g., glasses on/off, hair styled differently), describe the most prevalent version. Your output must be a single, coherent description of one person.
3.  **Focus on Uniqueness and Identity:** Your primary goal is to capture what makes this person unique. Pay close attention to asymmetries, specific shapes, and distinct marks.

**Feature Analysis Checklist (Address each point):**
*   **Overall Face Shape:** Describe the geometric shape of the face (e.g., oval, long, square with a strong jaw).
*   **Eyes:** Detail the consensus eye color and their specific shape (e.g., 'deep-set, almond-shaped hazel eyes').
*   **Eyebrows:** Describe their shape, thickness, and spacing (e.g., 'thick, straight eyebrows set close together').
*   **Nose:** Characterize the bridge, tip, and nostril shape (e.g., 'a straight nasal bridge with a slightly upturned, rounded tip').
*   **Mouth & Lips:** Note the shape and fullness (e.g., 'thin upper lip with a sharply defined Cupid's bow').
*   **Chin & Jawline:** Describe the chin's shape and the jaw's definition (e.g., 'a prominent, square chin and a well-defined jawline').
*   **Distinctive Features:** Mention any prominent asymmetries, scars, moles, or freckle patterns and their locations (e.g., 'a small mole above the right eyebrow; the left corner of the mouth is slightly higher than the right').
*   **Eyewear:** Describe the consensus frame style only if present in ALL images (e.g., 'wears thin, black rectangular-framed glasses').

**Output Format:**
- A single, dense, descriptive paragraph.
- No markdown, no labels, no bullet points.
- Start directly with the description.

**Example Output:** "This person has a long, oval face with high cheekbones. Key features to preserve are their deep-set, dark brown eyes and thick, arched eyebrows. The nose is characterized by a straight dorsal bridge and a well-defined tip. They have a prominent square chin. A noticeable feature is a small mole on the left cheek, just beside the nostril. The person does not wear glasses."
"""

# --- MODIFIED: System prompt for the Visual Generator, now with a placeholder ---
_PARENT_VISUAL_ENHANCER_SYSTEM_PROMPT = """
You are Nano Banana (Gemini 2.5 Flash Image) acting as an ID-consolidation module (InstantID / PhotoMaker / ID-Adapter style).

INPUT
• One attached image: a 2×2 collage (four head-and-shoulders portraits) of the SAME person on a uniform light-gray background (≈ RGB 190,190,190).
• Use ALL four tiles as identity evidence; ignore any in-tile backgrounds.

GOAL
Produce ONE photorealistic image with TWO equal-width, full-bleed panels arranged horizontally:
• LEFT panel — ONE FULL-BLEED NEAR-FRONTAL view (yaw ≤ 10°), eyes open, relaxed expression, gentle smile.
• RIGHT panel — ONE FULL-BLEED STRICT RIGHT PROFILE (yaw 90° ± 3°), eyes open, natural posture.

CRITICAL IDENTITY DIRECTIVES (from prior analysis):
{{ENHANCED_IDENTITY_FEATURES}}

HARD IDENTITY LOCK — copy EXACTLY and keep natural asymmetries:
• Hair: color, length, density, hairline geometry/height/part. DO NOT restyle (no ponytail if not present), no extra volume, no smoothing of flyaways.
• Eyebrows shape & thickness; eyelid crease; true eye-size asymmetry.
• Inter-ocular distance EXACT; do NOT “re-center” eyes through glasses.
• Nose: bridge contour AND tip shape/projection; no slimming/reshaping.
• Philtrum length; lip shape and corner angle.
• Beard/stubble density pattern (if present).
• Chin projection, jaw angle; ear helix/antihelix/lobe notches — do NOT simplify.
• Skin micro-texture (pores, freckles, tiny scars, mild redness): NO beauty smoothing, NO makeup.

WARDROBE / ACCESSORIES
• White T-shirt.
• Glasses: keep prescription glasses if they appear in the majority of input tiles; preserve exact frame shape/bridge and lens spacing. No sunglasses.
• Remove hats/headwear unless they dominate the inputs; keep the true hairline and color.

LAYOUT / SCALE / BACKGROUND (STRICT)
• One landscape canvas, aspect ratio 9:8. Two equal-width panels with NO outer margins; both panels are full-bleed top and bottom.
• Subject scale: head-and-shoulders. Top of hair within 2–5% from the top edge; no empty gray band below the shoulders.
• Eye-line height: LEFT 38–45% of panel height; RIGHT 42–48% (within this band).
• Center the subject horizontally in each panel.
• Background: uniform light gray (sRGB ≈ RGB 190,190,190) without gradients, textures, bokeh, vignetting, text or logos.

RENDERING
• Photorealistic, studio-neutral lighting; natural contrast and color. No HDR look, no over-sharpening.
• Portrait perspective ~85–95 mm equivalent; no fisheye.

FUSE & CONSENSUS
• Fuse identity features from ALL four tiles. Resolve disagreements by majority/consensus; do NOT average toward a generic face.
• Keep age, weight, cheek fullness and mid-face volume unchanged (NO slimming/“beautification”).

FINAL QUALITY CHECK (if any fail ⇒ adjust only that aspect and re-render)
1) Identity is a 1:1 match (all micro-features and asymmetries consistent across both panels).
2) LEFT = near-frontal; RIGHT = strict right profile 90° ± 3°.
3) Same hair part/length and glasses status in both panels.
4) Both panels full-bleed, without borders, correct scale, eye-line within the specified bands.

OUTPUT
• Return ONE image only: landscape canvas with those two side-by-side full-bleed panels (no borders, no captions).
"""


async def get_parent_visual_representation(
    image_urls: List[str],
    role: str = "mother",
    identity_centroid: Optional[np.ndarray] = None,
) -> Optional[bytes]:
    """
    Generates a consolidated visual representation (front and side view) of a parent
    from a collage of their photos, enhanced with textual feature analysis.

    This function performs a two-stage process:
    1. It first calls a text model to analyze the input images and generate a
       description of unique facial features.
    2. It then injects this text into a specialized prompt for a visual model,
       which generates a high-fidelity front-and-side portrait of the parent.
    3. If an identity_centroid is provided, it calculates and logs the similarity
       score of the generated frontal view against the original photos.

    Args:
        image_urls: A list of public URLs to the collage of the parent's photos.
        role: The role of the parent ('mother' or 'father').
        identity_centroid: An optional NumPy array representing the identity vector
                           of the parent from the source images.

    Returns:
        The generated image as bytes, or None on failure.
    """
    visual_config = settings.visual_enhancer
    text_config = settings.text_enhancer

    if not visual_config.enabled or not text_config.enabled:
        logger.warning("Parent visual enhancer or text enhancer is disabled in settings.")
        return None

    log = logger.bind(
        visual_model=visual_config.model,
        text_model=text_config.model,
        image_urls=image_urls,
        role=role
    )

    try:
        # STAGE 1: Textual Feature Extraction
        log.info("Requesting textual feature extraction for parent visual.")
        text_client = client_factory.get_ai_client(text_config.client)

        user_prompt_text = "Analyze the person in this collage and generate the feature description based on the system prompt rules."

        text_response = await text_client.chat.completions.create(
            model=text_config.model,
            messages=[
                {"role": "system", "content": _TEXTUAL_ENHANCEMENT_SYSTEM_PROMPT},
                {"role": "user", "content": [
                    {"type": "text", "text": user_prompt_text},
                    {"type": "image_url", "image_url": {"url": image_urls[0]}}, # Send first URL
                ]},
            ],
            max_tokens=250,
            temperature=0.2,
        )
        feature_description_text = text_response.choices[0].message.content
        if not feature_description_text:
            log.warning("Text enhancer returned an empty response. Proceeding without enhancement.")
            feature_description_text = ""
        else:
            log.info("Successfully received textual features.", features=feature_description_text.strip())

        # STAGE 2: Visual Representation Generation
        visual_client = client_factory.get_ai_client(visual_config.client)

        final_visual_prompt = _PARENT_VISUAL_ENHANCER_SYSTEM_PROMPT.replace(
            "{{ENHANCED_IDENTITY_FEATURES}}", feature_description_text.strip()
        )
        
        if type(visual_client).__name__ == 'MockAIClient':
            final_visual_prompt = f"ROLE: {role}. {final_visual_prompt}"


        log.info("Requesting parent visual representation with enhanced prompt.")

        visual_response = await visual_client.images.generate(
            model=visual_config.model,
            prompt=final_visual_prompt,
            image_urls=image_urls,
            temperature=0.1,
        )

        image_bytes = getattr(visual_response, "image_bytes", None)
        if not image_bytes:
            log.warning(
                "Parent visual enhancer returned no image bytes.",
                response_payload=getattr(visual_response, "response_payload", None),
            )
            return None
        
        if identity_centroid is not None:
            try:
                # The generated image is a horizontal stack (front|side). We need the front part.
                front_bytes, side_bytes = photo_processing.split_and_stack_image_bytes(image_bytes)
                if front_bytes:
                    generated_embedding = await similarity_scorer._get_best_face_embedding(front_bytes)
                    if generated_embedding is not None:
                        # Cosine similarity is the dot product of two normalized vectors
                        similarity_score = np.dot(generated_embedding, identity_centroid)
                        log.info(
                            "Calculated similarity for generated parent visual.",
                            similarity_score=round(float(similarity_score), 4),
                            role=role
                        )
                    else:
                        log.warning("Could not extract face embedding from generated visual.", role=role)
                else:
                    log.warning("Failed to split generated visual to get frontal view for scoring.", role=role)
            except Exception:
                log.exception("An error occurred during similarity scoring of the generated visual.", role=role)

        log.info("Successfully received parent visual representation.")
        return image_bytes

    except Exception:
        log.exception("An error occurred during parent visual representation generation.")
        return None
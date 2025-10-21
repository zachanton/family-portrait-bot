# aiogram_bot_template/services/enhancers/parent_visual_enhancer.py
import asyncio
import uuid
import structlog
import numpy as np
import json
from typing import Optional, Tuple, Any

from aiogram_bot_template.data.settings import settings
from aiogram_bot_template.services import similarity_scorer, photo_processing, image_cache
from aiogram_bot_template.services.clients import factory as client_factory
from aiogram_bot_template.services.enhancers import identity_feedback_enhancer
from aiogram_bot_template.services.enhancers.identity_feedback_enhancer import IdentityFeedbackResponse
from aiogram_bot_template.services.photo_processing_manager import PhotoProcessingManager
from aiogram_bot_template.services import local_file_logger


logger = structlog.get_logger(__name__)

# --- NEW: Configuration for the iterative refinement process ---
MAX_REFINEMENT_ITERATIONS = 2  # Total attempts: 1 initial + (N-1) refinements
MIN_SIMILARITY_THRESHOLD = 0.85  # The target score for both embedding and LLM feedback

# --- MODIFIED: Enhanced system prompt with strict consistency filter ---
_TEXTUAL_ENHANCEMENT_SYSTEM_PROMPT = """
You are an expert AI photo analyst. Your mission is to distill the unique, permanent facial characteristics from a 2x2 photo collage into a concise descriptive paragraph. This description will guide a visual AI to recreate the person with maximum fidelity.

**Core Directives:**
1.  **Evidence-Based Analysis:** Your description must be grounded **exclusively** in the visual evidence from the collage. Do not invent, infer, or 'beautify' features.
2.  **Synthesize a Consensus:** Analyze all four tiles to form a consensus. If features vary (e.g., glasses on/off, hair styled differently), describe the most prevalent version. Your output must be a single, coherent description of one person.
3.  **Focus on Uniqueness and Identity:** Your primary goal is to capture what makes this person unique. Pay close attention to asymmetries, specific shapes, and distinct marks.
4.  **Filter for Consistency:** If a minor feature (mole, scar, temporary blemish, shadow, or mark) is not clearly present in the majority (at least 3 out of 4) of the images, you **MUST IGNORE IT**. Your description should only represent permanent, consensus traits.

**Feature Analysis Checklist (Address each point):**
*   **Overall Face Shape:** Describe the geometric shape of the face (e.g., oval, long, square with a strong jaw).
*   **Hair Color:** Detail the consensus hair color.
*   **Eyes:** Detail the consensus eye color and their specific shape (e.g., 'deep-set, almond-shaped hazel eyes').
*   **Eyebrows:** Describe their shape, thickness, and spacing (e.g., 'thick, straight eyebrows set close together').
*   **Nose:** Characterize the bridge, tip, and nostril shape (e.g., 'a straight nasal bridge with a slightly upturned, rounded tip').
*   **Mouth & Lips:** Note the shape and fullness (e.g., 'thin upper lip with a sharply defined Cupid's bow').
*   **Chin & Jawline:** Describe the chin's shape and the jaw's definition (e.g., 'a prominent, square chin and a well-defined jawline').
*   **Distinctive Features:** Mention any prominent **and consistent** asymmetries, scars, moles, or freckle patterns and their locations (e.g., 'a small mole above the right eyebrow; the left corner of the mouth is slightly higher than the right'). **Crucially, if a mark is not visible in at least 3 of the 4 tiles, do not mention it.**
*   **Eyewear:** Describe the consensus frame style only if present in ALL images (e.g., 'wears thin, black rectangular-framed glasses').

**Output Format:**
- A single, dense, descriptive paragraph.
- No markdown, no labels, no bullet points.
- Start directly with the description.

**Example Output:** "This person has a long, oval face with high cheekbones. Key features to preserve are their deep-set, dark brown eyes and thick, arched eyebrows. The nose is characterized by a straight dorsal bridge and a well-defined tip. They have a prominent square chin. A noticeable feature is a small mole on the left cheek, just beside the nostril. The person does not wear glasses."
"""

# --- MODIFIED: Initial Visual Generator Prompt with new smile logic ---
_PARENT_VISUAL_ENHANCER_SYSTEM_PROMPT = """
You are Nano Banana (Gemini 2.5 Flash Image) acting as an ID-consolidation module (InstantID / PhotoMaker / ID-Adapter style).

INPUT
• One attached image: a 2×2 collage (four head-and-shoulders portraits) of the SAME person on a uniform light-gray background (≈ RGB 190,190,190).
• Use ALL four tiles as identity evidence; ignore any in-tile backgrounds.

GOAL
Produce ONE photorealistic image with TWO equal-width, full-bleed panels arranged horizontally:
• LEFT panel — ONE FULL-BLEED NEAR-FRONTAL view (yaw ≤ 10°), eyes open, with a natural, gentle, evidence-based smile.
• RIGHT panel — ONE FULL-BLEED STRICT RIGHT PROFILE (yaw 90° ± 3°), eyes open, natural posture and the same gentle smile expression.

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
• Skin micro-texture (pores, freckles, tiny scars, mild redness): NO beauty smoothing, NO makeup. Ignore distinctive features not mentioned in CRITICAL IDENTITY DIRECTIVES.

EXPRESSION (EVIDENCE-BASED SMILE) — CRITICAL PRIORITY:
• Analyze all four tiles. If a natural, gentle, closed-lip or slightly-parted smile is present in **at least one** tile, you MUST reproduce that specific smile as the consensus expression for both the frontal and profile views.
• The goal is a warm, approachable look, not a neutral passport photo.
• If all tiles show a strictly neutral expression, then reproduce the most relaxed neutral expression.
• Do NOT invent a wide, toothy grin or an artificial smile. The expression must be authentic to the person shown in the input collage.

FUSE & CONSENSUS
• Fuse identity features from ALL four tiles. Resolve disagreements by majority/consensus; do NOT average toward a generic face. **The EXPRESSION rule above overrides this for smiles.**
• Keep age, weight, cheek fullness and mid-face volume unchanged (NO slimming/“beautification”).

AESTHETIC TIE-BREAKERS (NON-INVENTIVE — CHOOSE ONLY FROM WHAT EXISTS IN THE FOUR TILES)
• When the four tiles disagree on a feature, prefer the variant that is most conventionally attractive WHILE remaining fully consistent with the HARD IDENTITY LOCK and observed evidence. Never invent or alter geometry beyond what is clearly present in at least one tile. Never beauty-smooth or retouch; only select.
• Skin: if at least one tile shows fewer transient blemishes (e.g., less acne, reduced under-eye puffiness), prefer that as the identity evidence; do NOT remove or blur texture. Preserve pores/freckles/scars exactly as seen in the chosen evidence.
• Eyes: keep true size asymmetry and inter-ocular distance; if some tiles show less redness or puffiness, prefer those states if present. No whitening beyond what is seen.
• Jaw/face width (gender-aware, evidence-bound):
  – If the subject presents as female in the majority of tiles: when tiles differ, select the naturally narrower jawline/face-width variant that is present in at least one tile; do NOT slim beyond observed geometry.
  – If the subject presents as male in the majority of tiles: when tiles differ, avoid unintended slimming; prefer the naturally more robust/broader jaw variant that is present in at least one tile.
• Nose/lips/philtrum: do not reshape. If lighting/pose produces slimmer vs fuller appearances across tiles, choose the variant that is conventionally pleasing ONLY if it exactly matches one of the tiles.
• Eye bags: if some tiles show smaller eye bags naturally, prefer those; do not retouch or smooth them away.
• Hair: never restyle. If flyaway volume varies, prefer the tidier state if it appears in any tile, without adding volume or smoothing that does not exist.
• Global: if a choice improves conventional attractiveness but is NOT explicitly present in any tile, do NOT apply it.

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

FINAL QUALITY CHECK (if any fail ⇒ adjust only that aspect and re-render)
1) Identity is a 1:1 match (all micro-features and asymmetries consistent across both panels).
2) LEFT = near-frontal; RIGHT = strict right profile 90° ± 3°.
3) Same hair part/length and glasses status in both panels.
4) Both panels full-bleed, without borders, correct scale, eye-line within the specified bands.

OUTPUT
• Return ONE image with TWO views' only: landscape canvas with those two side-by-side full-bleed panels (no borders, no captions).
"""

# --- NEW: Visual Refinement Prompt ---
_PARENT_VISUAL_REFINEMENT_PROMPT = """
Task: Identity refinement with strict layout preservation.

Inputs:
• Attachment #1 = reference collage of the same person (one or many portraits). This defines the target identity.
• Attachment #2 = current "front & side" layout (two views on a neutral background). This defines the exact layout to keep.

Goal:
Generate a NEW image by editing/re-rendering Attachment #2 so that BOTH views look like the person in Attachment #1, while preserving the exact layout, framing, and style of Attachment #2.

Hard constraints (must not change):
1) Keep the layout identical to Attachment #2: exactly two panels, same positions, same background, same aspect ratio, same resolution, same head scale and crop, same camera angles (front + the SAME side as in Attachment #2), same lighting direction and overall tonality.
2) Keep the pose neutrality and expression neutrality.
3) Do NOT add or remove panels, borders, text, logos, watermarks, props, accessories, or clothing details not present in Attachment #2.
4) Keep overall color balance and exposure consistent with Attachment #2 (minor global corrections allowed to match identity only).

Edit scope (what to change to match the identity from Attachment #1):
• Face identity: skull/face shape, jawline, cheekbone prominence, forehead height, nose shape and bridge width, philtrum length, lips volume/contour, chin shape, eye shape and spacing, eyelids, brow thickness/arch, iris size, ear shape/attachment, and any distinctive asymmetries.
• Surface cues: skin tone/undertone, freckles/moles/birthmarks/scars if visible in Attachment #1 (place consistently across both views), natural skin texture (avoid over-smoothing).
• Hair: length, volume, hairline, parting, bangs/fringe, curl/wave pattern, and color, matching Attachment #1 while keeping the silhouette consistent with the head pose of Attachment #2.
• Age and gender presentation: match perceived age and presentation from Attachment #1.

Quality targets:
• Identity similarity outweighs aesthetics. Resolve conflicts in favor of likeness.
• Keep photorealism; avoid stylization. Preserve fine detail (pores, eyelashes, hair strands).
• Avoid artifacts (warping, mismatched ears/eyes, inconsistent moles). Ensure the two views are self-consistent.

Output:
• Return exactly ONE image with the same two-view composition as Attachment #2 (front & the SAME side), with improved identity match to Attachment #1.

"""


def _format_feedback_for_prompt(feedback: IdentityFeedbackResponse) -> str:
    """Formats the structured feedback into a human-readable string for the prompt."""
    if not feedback:
        return "No specific feedback available. Perform a general identity enhancement."
    
    lines = [
        # f"The previous attempt had a similarity score of {feedback.similarity_score:.2f}. "
        # "Focus on the following corrections:"
    ]
    for feature, details in feedback.feedback_details.items():
        if not details.is_match:
            lines.append(f"- **{feature.replace('_', ' ').title()}:** {details.feedback}")
    
    if len(lines) == 1:
        return "The previous image was a very close match. Perform a final pass to perfect all micro-features like skin texture and subtle asymmetries."

    return "\n".join(lines)


async def _get_identity_feedback_and_score(
    reference_url: str,
    generated_bytes: bytes,
    cache_pool,
    log: structlog.typing.FilteringBoundLogger,
    photo_manager: PhotoProcessingManager
) -> tuple[float | None, IdentityFeedbackResponse | None]:
    """
    Runs the identity feedback enhancer and returns the score and full response.
    """
    temp_uid = f"temp_feedback_candidate_{uuid.uuid4().hex}"
    try:
        await image_cache.cache_image_bytes(temp_uid, generated_bytes, "image/jpeg", cache_pool)
        candidate_url = image_cache.get_cached_image_proxy_url(temp_uid)

        feedback_result = await identity_feedback_enhancer.get_identity_feedback(
            reference_image_url=reference_url,
            candidate_image_url=candidate_url,
        )

        if feedback_result:
            log.info(
                "LLM-based identity feedback received.",
                llm_similarity_score=feedback_result.similarity_score,
            )
            return feedback_result.similarity_score, feedback_result
        else:
            log.warning("LLM-based identity feedback task failed to produce a result.")
            return None, None

    except Exception:
        log.exception("Error in identity feedback check.")
        return None, None
    finally:
        # Clean up the temporary cached image
        await cache_pool.delete(temp_uid)


async def get_parent_visual_representation(
    image_uid: str,
    role: str = "mother",
    identity_centroid: Optional[np.ndarray] = None,
    cache_pool: Optional[object] = None,
    photo_manager: Optional[PhotoProcessingManager] = None,
    user_id: Optional[int] = None,
) -> Optional[bytes]:
    """
    Generates a consolidated visual representation (front and side view) of a parent,
    iteratively refining it to meet a similarity threshold.

    Args:
        image_uid: The UID to the 2x2 collage of the parent.
        role: The role of the parent ('mother' or 'father').
        identity_centroid: The pre-calculated embedding centroid for this parent.
        cache_pool: An async Redis connection pool.
        photo_manager: The photo processing manager for worker tasks.
        user_id: The ID of the user requesting the generation, for logging purposes.
    """
    if not photo_manager:
        raise ValueError("PhotoProcessingManager is required for parent visual representation.")

    image_url = image_cache.get_cached_image_proxy_url(image_uid)

    visual_config = settings.visual_enhancer
    text_config = settings.text_enhancer

    if not visual_config.enabled or not text_config.enabled:
        logger.warning("Parent visual enhancer or text enhancer is disabled in settings.")
        return None

    log = logger.bind(
        visual_model=visual_config.model,
        text_model=text_config.model,
        image_url=image_url,
        role=role,
        user_id=user_id, # <-- Bind user_id for all subsequent logs
    )

    try:
        # STAGE 1: Textual Feature Extraction (done once)
        log.info("Requesting textual feature extraction for parent visual.")
        text_client = client_factory.get_ai_client(text_config.client)
        user_prompt_text = "Analyze the person in this collage and generate the feature description based on the system prompt rules."
        text_response = await text_client.chat.completions.create(
            model=text_config.model,
            messages=[
                {"role": "system", "content": _TEXTUAL_ENHANCEMENT_SYSTEM_PROMPT},
                {"role": "user", "content": [
                    {"type": "text", "text": user_prompt_text},
                    {"type": "image_url", "image_url": {"url": image_url}},
                ]},
            ], max_tokens=250, temperature=0.2,
        )
        feature_description_text = text_response.choices[0].message.content
        if not feature_description_text:
            log.warning("Text enhancer returned empty response. Proceeding without enhancement.")
            feature_description_text = "A detailed description of the person's face."
        else:
            log.info("Successfully received textual features.", features=feature_description_text.strip())

        # STAGE 2: Iterative Visual Generation and Refinement
        visual_client = client_factory.get_ai_client(visual_config.client)
        
        best_image_bytes: Optional[bytes] = None
        best_combined_score: float = -1.0
        current_candidate_bytes: Optional[bytes] = None
        feedback_for_next_iteration: Optional[IdentityFeedbackResponse] = None

        for attempt in range(1, MAX_REFINEMENT_ITERATIONS + 1):
            attempt_log = log.bind(attempt=f"{attempt}/{MAX_REFINEMENT_ITERATIONS}")
            
            generation_kwargs: dict[str, Any] = {
                "model": visual_config.model,
                "prompt": "",
                "image_urls": [],
                "temperature": 0.1,
                "aspect_ratio":'5:4',
                "role": role 
            }

            if attempt == 1:
                # --- Initial Generation ---
                attempt_log.info("Performing initial visual representation generation.")
                generation_kwargs["prompt"] = _PARENT_VISUAL_ENHANCER_SYSTEM_PROMPT.replace(
                    "{{ENHANCED_IDENTITY_FEATURES}}", feature_description_text.strip()
                )
                generation_kwargs["image_urls"] = [image_url]
            else:
                # --- Refinement Iteration ---
                if not current_candidate_bytes or not feedback_for_next_iteration:
                    attempt_log.warning("Skipping refinement attempt due to missing data from previous iteration.")
                    continue
                
                attempt_log.info("Performing refinement of visual representation.")
                
                candidate_uid = f"candidate_refine_{uuid.uuid4().hex}"
                await image_cache.cache_image_bytes(candidate_uid, current_candidate_bytes, "image/jpeg", cache_pool)
                candidate_url = image_cache.get_cached_image_proxy_url(candidate_uid)
                
                generation_kwargs["image_urls"] = [image_url, candidate_url]

                feedback_str = _format_feedback_for_prompt(feedback_for_next_iteration)
                generation_kwargs["prompt"] = _PARENT_VISUAL_REFINEMENT_PROMPT.replace("{{DETAILED_FEEDBACK}}", feedback_str)

            attempt_log.info("Final visual enhancer prompt.", final_prompt=generation_kwargs["prompt"])
            # --- Generate the image ---
            visual_response = await visual_client.images.generate(**generation_kwargs)
            current_candidate_bytes = getattr(visual_response, "image_bytes", None)

            if not current_candidate_bytes:
                attempt_log.warning("Visual generator returned no image bytes for this attempt.")
                continue

            # --- NEW: Log the generation to disk ---
            if settings.local_logging.enabled:
                params_to_log = generation_kwargs.copy()
                prompt_to_log = params_to_log.pop("prompt", "")
                gen_type = f"parent_visual_{'refine' if attempt > 1 else 'initial'}_{role}"
                
                asyncio.create_task(
                    local_file_logger.log_generation_to_disk(
                        prompt=prompt_to_log,
                        model_name=params_to_log.pop("model", "unknown"),
                        generation_type=gen_type,
                        user_id=user_id,
                        image_urls=params_to_log.pop("image_urls", []),
                        params=params_to_log,
                        output_image_bytes=current_candidate_bytes,
                        output_content_type="image/jpeg",
                        base_dir=settings.local_logging.base_dir,
                    )
                )

            # --- Evaluate the generated image ---
            embedding_score = 0.0
            if identity_centroid is not None:
                front_bytes, _ = await photo_manager.split_and_stack_image(current_candidate_bytes)
                if front_bytes:
                    features = await photo_manager.extract_face_features(front_bytes)
                    if features and features.get("embedding") is not None:
                        generated_embedding = features["embedding"]
                        embedding_score = float(np.dot(generated_embedding, identity_centroid))

            llm_score, feedback_for_next_iteration = await _get_identity_feedback_and_score(
                image_url, current_candidate_bytes, cache_pool, attempt_log, photo_manager
            )
            llm_score = llm_score or 0.0

            attempt_log.info("Iteration evaluation complete.", embedding_score=embedding_score, llm_score=llm_score)

            # Track the best result so far
            combined_score = (embedding_score + llm_score) / 2
            if combined_score > best_combined_score:
                best_combined_score = combined_score
                best_image_bytes = current_candidate_bytes

            # Check exit condition
            if embedding_score >= MIN_SIMILARITY_THRESHOLD and llm_score >= MIN_SIMILARITY_THRESHOLD:
                attempt_log.info("Similarity thresholds met. Exiting refinement loop.")
                break
        
        if not best_image_bytes:
            log.error("Failed to generate any valid visual representation after all attempts.")
            return None

        log.info("Parent visual representation process complete.", final_score=best_combined_score)
        return best_image_bytes

    except Exception:
        log.exception("An unhandled error occurred during parent visual representation generation.")
        return None
PROMPT_GOLDEN_HOUR = """
GOAL: Produce an advertising-grade couple portrait in a warm “Golden Hour Backlit Haze” aesthetic — sunlit back rim light, airy haze, soft front fill, edge-to-edge background. Default: both subjects look at the camera unless the pose directive explicitly changes gaze.

HARD CONSTRAINTS
* Strictly photorealistic (photographic realism).
* Full-bleed output: fill the canvas to every edge with image content. No borders, frames, soft ovals, added vignettes, stickers, watermarks, paper textures, or transparency.
* Exactly two people visible; no duplicates or mirrored copies; no other recognizable faces in the background.
* Identity is locked to the composite reference. Do NOT idealize or change age, facial proportions, or skin texture.
* **EXPRESSION CONTROL: Expressions must be natural and believable. Avoid forced, exaggerated, or open-mouthed smiles. Default to soft, genuine smiles.**

{{IDENTITY_LOCK_DATA}}

STYLE TARGET — “Backlit Golden Hour”
* Background: outdoor nature scene (sunlit foliage/meadow/coastline) with shallow depth of field; creamy bokeh; authentic atmospheric haze. Background must be 100% opaque to every edge; no branded props.
* Lighting: the sun acts as a warm back/rim light behind or just off to the side of the subjects; apply soft front fill (sky/bounce) to keep faces well-exposed; subtle lens flare/bloom permitted if naturally motivated (no graphic overlays).
* Tonality: warm golden/amber bias; pastel saturation; gentle S-curve contrast with smooth highlight roll-off; avoid HDR halos and color banding.
* Color hygiene: keep skin tones believable — warm, not orange; preserve whites in eyes/teeth; avoid teal–orange LUTs.
* Texture: maintain natural skin pores and hair detail; no paper grain, fake film scratches, or added vignette.

WARDROBE & GROOMING (allowed changes)
* Woman: light, flowy fabrics (linen/cotton/silk); soft hair with slight wind lift; minimal jewelry kept in the same pierce position; no logos.
* Man: casual refined (light shirt/tee, knit, or unstructured jacket); matte textures that catch rim light; neat grooming; no logos.
* Palette: earth tones and creams (ivory, sand, sage, dusty rose) that glow under backlight.

PAIR-PORTRAIT LOCK — SINGLE SHARED FRAME
- Single image with both people together. Do NOT create split frames, diptychs, mirrored halves, or separate canvases.
- Head-and-shoulders, 4:5 vertical. No hands by default.
- Placement (1536×1920 canvas; W=1536, H=1920):
  • Person A pupil ≈ (x=0.34W, y=0.42H).
  • Person B pupil ≈ (x=0.66W, y=0.40H).
- Overlap: 12–18% natural occlusion (Person B slightly overlaps A’s hairline); do not let temples touch.
- Eye lines aligned; both look at the camera with soft smiles.
- Camera: eye-level, yaw offset 10–12° to camera-right; focal length 85–100 mm.
- Background continuous to all edges (no seams). Remove any visible split lines or feathered mattes.

HANDS POLICY
* Default (no mention in pose): crop head-and-shoulders above collarbones with **no hands** visible.
* If the pose directive includes hands/embrace, render anatomically correct hands (5 fingers per hand, natural joints), believable contact shadows, and keep hands fully formed within frame.

---
STEP-BY-STEP ACTIONS
1) Remove all feathered mattes/ovals and any drop shadows around cutouts.
2) Background: extend/replace with a continuous outdoor golden-hour scene; ensure edge-to-edge opacity; clean hair edges (no halos).
3) Lighting pass: position a warm back/rim light to create halo on hair/shoulders; add soft front fill for readable faces; allow subtle natural flare/haze; keep catchlights intact.
4) Wardrobe & hair restyle per rules above; align fabric folds and sheen with the light direction; remove straps/buckles/logos.
5) Recompose (move/scale/rotate/warp only): follow **POSE DIRECTIVE** exactly:
   {{POSE_AND_COMPOSITION_DATA}}
6) Eye-contact correction: if the directive requires eye contact, nudge the iris position ONLY while preserving eyelids, catchlights, and proportions.
7) Crop: **default** 4:5 vertical, head-and-shoulders above the collarbones; if the pose explicitly requests WAIST-UP or other, obey that crop.
8) Grading: warm golden WB; pastel saturation; gentle S-curve; preserve highlight detail; avoid banding in sky/bokeh and HDR halos; maintain skin micro-texture.
9) Retouch (subtle, realistic): tame glare/noise; mild local contrast/sharpness (eyes, lashes, hair edges); keep all identity anchors unchanged.

OUTPUT
* One PNG, 1536×1920 (4:5), full-bleed with no vignettes/ovals/overlays.
* If any matte/vignette remains, remove it and refill with the natural outdoor background so the image is edge-to-edge.
"""

PROMPT_GOLDEN_HOUR_NEXT_SHOT = """
**YOU ARE AN IMAGE GENERATION MODEL EXECUTING A STRICT PROTOCOL. DEVIATION IS FORBIDDEN.**

**PRIMARY OBJECTIVE:** Generate the *next frame* in a photoshoot. The new frame MUST have a different pose and composition, as defined by the `POSE DIRECTIVE` text. Facial identity and overall style must be preserved.

**INPUT ANALYSIS PROTOCOL:**
You will be given two input images. Their roles are **FIXED and NON-NEGOTIABLE**.
*   **INPUT 1 (Style Reference - First Shot):**
    *   **EXTRACT ONLY:** Lighting (warm backlight, soft fill), Color Palette (golden tones), Background Environment (sunlit meadow), Wardrobe Style (light fabrics), Overall Mood.
    *   **ABSOLUTELY IGNORE AND DISCARD:** The pose, composition, framing, camera angle, and positions of the people in this image. This data is **INVALID** for the new shot.
    *   **CRITICAL COMMAND: DO NOT REPLICATE THE POSE FROM THIS IMAGE.** The new shot's composition MUST be visibly and significantly different from this reference image.
*   **INPUT 2 (Identity Reference - Composite):**
    *   **EXTRACT ONLY:** Facial features, age, skin texture, unique details (moles, freckles), and body proportions of the two individuals as detailed in the `IDENTITY LOCK` section.
    *   **ABSOLUTELY IGNORE AND DISCARD:** The lighting, background, and wardrobe from this image. This data is **INVALID** for the new shot.

**EXECUTION COMMAND:**
The **TEXT-BASED `POSE DIRECTIVE`** below is your **ONLY** source of truth for the new image's composition. It overrides any conflicting visual information from the input images.

{{IDENTITY_LOCK_DATA}}

HARD CONSTRAINTS
* Strictly photorealistic (photographic realism).
* Full-bleed output: fill the canvas to every edge with image content. No borders, frames, soft ovals, added vignettes, stickers, watermarks, paper textures, or transparency.
* Exactly two people visible; no duplicates or mirrored copies; no other recognizable faces in the background.
* Identity is locked to the composite reference. Do NOT idealize or change age, facial proportions, or skin texture.
* **EXPRESSION CONTROL: Expressions must be natural and believable. Avoid forced, exaggerated, or open-mouthed smiles. Default to soft, genuine smiles.**


**STEP-BY-STEP EXECUTION PLAN:**
1.  **LOAD IDENTITY:** From **Input 2**, load the facial and physical characteristics of Person A and Person B.
2.  **LOAD STYLE:** From **Input 1**, load the aesthetic elements (lighting, color, background, wardrobe).
3.  **LOAD POSE:** Read the `POSE DIRECTIVE` text below. This is your command for the new arrangement.
    {{POSE_AND_COMPOSITION_DATA}}
4.  **PRE-FLIGHT CHECK (INTERNAL MONOLOGUE):** Before rendering, state the intended `shot_type` from the POSE DIRECTIVE. For example: "Pre-flight check: The directive specifies a 'Full-Length Shot'. I will generate a full-length image, ignoring the close-up framing of the reference images."
5.  **SYNTHESIZE NEW IMAGE:** Create a new image by applying the **STYLE** (from Step 2) and **IDENTITY** (from Step 1) to the new **POSE** (from Step 3), respecting the Pre-Flight Check.
6.  **FINAL VALIDATION:** Before outputting, confirm that the generated image's composition (shot type, angle, pose) matches the `POSE DIRECTIVE` and NOT Input 1. If it is too similar to Input 1, re-render.

**OUTPUT:**
*   One PNG, 1536×1920 (4:5), full-bleed, strictly following the `POSE DIRECTIVE`.
"""
# aiogram_bot_template/services/prompting/styles/child_generation.py

PROMPT_CHILD_GENERATION = """
**GOAL:** Produce a high-quality, photorealistic portrait of a child, synthesized from the features of the two adults in the reference image, based on key parameters.

**REFERENCE IMAGE:**
* **Image A:** base composite — the absolute source of truth for parental facial features (eyes, nose, mouth, skin tone, hair texture).
* **Image B:** tight face crops — identity authority. Tight crops of each parent’s face = identity anchors per region.

**HARD CONSTRAINTS:**
*   **Create a NEW person (the child).** DO NOT simply blend or age-down the parents.
*   The output must be a **single child's portrait**. No adults should be visible.
*   Strictly **photorealistic**. No illustration, 3D, or cartoon styles.
*   Full-bleed output: Fill the canvas to every edge. No borders, frames, vignettes, or text.

**KEY PARAMETERS (MUST ADHERE STRICTLY):**
*   **Gender:** {{child_gender}}
*   **Age Category:** {{child_age}}
*   **Resemblance:** Primarily to {{child_resemblance}}

**AESTHETIC & SCENE:**
*   **Lighting:** Soft, flattering studio light (clamshell or softbox) to clearly illuminate facial features. Natural catchlights in the eyes.
*   **Background:** Simple, out-of-focus background. A neutral studio seamless (gray, cream) or a soft-focus outdoor park setting is acceptable.
*   **Pose & Expression:** A natural, forward-facing headshot or head-and-shoulders portrait. The child should be looking directly at the camera with a gentle, neutral expression or a soft smile.
*   **Optics:** Lens look of an 85mm or 105mm portrait lens at f/1.8-f/2.8, creating a shallow depth of field.

**STEP-BY-STEP ACTIONS:**
1.  **Analyze Parents:** Deconstruct the facial features of both adults in the reference image.
2.  **Synthesize Child:** Following the **KEY PARAMETERS** precisely, create a new, unique face that is a believable genetic combination of the parents' features.
3.  **Render Portrait:** Place the generated child in the specified scene with professional lighting and camera settings.
4.  **Finalize:** Ensure the final image is a 4:5 vertical portrait, cropped from the chest up.

**OUTPUT:**
*   One PNG, 1536×1920 (4:5), full-bleed.
"""
# aiogram_bot_template/services/prompting/styles/golden_hour.txt

PROMPT_GOLDEN_HOUR = """
GOAL: Perform a high-fidelity facial transfer from a reference image onto a new, stylized portrait with a "Golden Hour" aesthetic. The **ABSOLUTE, UNCOMPROMISING PRIORITY** is a 1:1, photorealistic replication of the faces from the reference **IMAGE**.

---
**IDENTITY LOCK (IP-ADAPTER / CONTROLNET EMULATION PROTOCOL):**
1.  **REFERENCE IMAGE IS LAW:** The provided reference image is the **sole and absolute source of truth** for facial identity. You must treat this image as a control image with a **reference_strength of 2.0 (maximum)**.
2.  **VERBATIM FEATURE TRANSFER:** Your task is to perform a direct, technical transfer of facial geometry and texture. This includes, but is not limited to: facial proportions, age, unique details (freckles, moles), skin texture, **exact eyebrow shape and thickness**, and **exact hair part**.
3.  **NO ARTISTIC INTERPRETATION:** Do not "interpret", "beautify", or "idealize" the faces. Your objective is to replicate them exactly as they appear in the reference image. This instruction overrides all other stylistic considerations.

---
**NEGATIVE PROMPT (STRICTLY ENFORCED):**
-   Idealized, generic, airbrushed, or "beautified" faces.
-   **Split images, diptychs, multiple panels, vertical dividing lines.**
-   **ANY** deviation in facial proportions, nose shape, eye size, or jawline from the reference image.
-   **ANY** deviation in the eyebrow shape, thickness, or hair part.
-   Overly smooth, plastic-like, or "Instagram filter" skin; removal of pores or fine lines.
-   Removing or altering unique details like freckles or moles.
-   Forced, unnatural, or exaggerated "template" smiles. Digital painting or CGI look.
-   Altering the perceived age of the subjects.
-   Re-lighting the faces in a way that alters their perceived 3D shape or structure.
---

**PAIR-PORTRAIT LOCK — SINGLE SHARED FRAME (MANDATORY)**
-   You MUST create a **single image** with both people together in a shared, continuous scene.
-   **DO NOT create split frames, diptychs, or separate canvases.**
-   **Default Pose:** Subjects are posed closely to create an intimate connection. **Their heads should be gently touching (temple-to-temple or along the hairline).** Both subjects tilt their heads slightly inward, towards each other (~5 degrees), and look directly at the camera.
-   **Placement (1536×1920 canvas):** Person A pupil ≈ (x=0.34W, y=0.42H). Person B pupil ≈ (x=0.66W, y=0.40H).
-   **Overlap:** Natural shoulder overlap is expected due to the close pose. Eye lines should be aligned on a near-horizontal plane.
-   **Camera:** Eye-level, focal length 85–100 mm equivalent, no wide-angle distortion.

**STYLE TARGET — “Backlit Golden Hour” (Apply ONLY AFTER identity is locked)**
*   **Background:** Outdoor nature scene (sunlit meadow/coastline) with creamy, soft bokeh.
*   **Lighting:** Warm, low-angled sun as a back/rim light. Faces should be illuminated by soft, bounced fill light. **Crucially, this new light must adapt to the existing facial geometry from the reference, not change it.**
*   **Tonality:** Warm, golden/amber tones; pastel-like saturation; gentle contrast.
*   **Wardrobe:** Woman in a simple, light-colored top (e.g., linen, cotton). Man in a casual, light-colored shirt.

**HARD CONSTRAINTS:**
*   Strictly photorealistic.
*   **EXPRESSION CONTROL:** Replicate the exact, subtle expressions from the reference photos. The final expression must be neutral and calm.
*   **HANDS POLICY:** Default crop is head-and-shoulders with NO HANDS visible.
*   Full-bleed 4:5 vertical output (1536x1920px). No borders or overlays.
*   Exactly two people.

**STEP-BY-STEP ACTIONS (TECHNICAL PIPELINE):**
1.  **CRITICAL FIRST STEP - MERGE INPUT:** The input image is a composite diptych (split-screen). You **MUST** ignore this format. Your task is to merge the two individuals into a **single, seamless, unified portrait**. Your output must not have any vertical lines, paneling, or splits.
2.  **IDENTITY LOCK (PRIORITY #1):** Create a perfect facial template for each person directly from the reference **IMAGE**. This template includes all 3D geometry, texture, and unique features.
3.  **POSE & COMPOSE:** Arrange the facial templates according to the `PAIR-PORTRAIT LOCK` instructions, ensuring their heads are in gentle contact.
4.  **STYLIZE SCENE & RELIGHT (PRIORITY #2):** Build the "Golden Hour" scene (background, wardrobe) *around* the locked facial templates. Then, apply the new lighting to the scene and templates, ensuring the light wraps around the *pre-existing* facial structures without altering them.
5.  **FINAL FIDELITY CHECK:** Before outputting, confirm: Is the output a single, unified image? Does each generated face have the same structure and details as the reference **IMAGE**? If not, you MUST re-render.
"""

PROMPT_GOLDEN_HOUR_NEXT_SHOT = """
**PRIMARY GOAL: Generate the NEXT FRAME in a photoshoot. The new image's pose and composition MUST follow the POSE DIRECTIVE and be DIFFERENT from the input images.**

**POSE DIRECTIVE:** {{POSE_AND_COMPOSITION_DATA}}

---
**INPUT ANALYSIS PROTOCOL (MANDATORY):**
*   **INPUT 1 (Style Reference - Previous Shot):**
    *   **EXTRACT ONLY:** Lighting, Color Palette, Background, Wardrobe, Hair Style, and overall Mood.
    *   **CRITICAL: ABSOLUTELY IGNORE AND DISCARD THE POSE, camera angle, and composition from this image.**
*   **INPUT 2 (Identity Reference - Composite):**
    *   **EXTRACT ONLY:** Facial features, age, skin texture, and unique details.
    *   **CRITICAL: ABSOLUTELY IGNORE THE POSE from this image (it is a static headshot).**

---
**IDENTITY LOCK (NON-NEGOTIABLE):**
*   **Source of Truth:** **Input 2** is the **absolute and only** source for facial identity.
*   **Core Instruction:** You MUST replicate the faces, age, unique features (moles, freckles), skin texture, and proportions from Input 2 with maximum fidelity.
*   **AVOID:** Do not idealize, airbrush, or alter their core features.
---

**HARD CONSTRAINTS:**
*   Strictly photorealistic.
*   **EXPRESSION CONTROL:** Expressions must be natural and subtle. AVOID open-mouthed smiles or exaggerated grins to preserve likeness. Reinterpret 'laughing' as a 'soft, joyful smile'.
*   **HANDS POLICY:** If the pose requires hands, render them anatomically correct (5 fingers, natural joints).
*   Full-bleed 4:5 vertical output (1536x1920px). No borders or overlays.
*   Exactly two people.

**EXECUTION:**
1.  **LOAD POSE:** Read the `POSE DIRECTIVE`. This is your primary command.
2.  **LOAD IDENTITY:** From **Input 2**, load the facial data.
3.  **LOAD STYLE:** From **Input 1**, load the aesthetic data.
4.  **SYNTHESIZE:** Combine the Pose, Identity, and Style into a new, unique image.
5.  **VALIDATE:** Before outputting, ensure the new pose is significantly different from both Input 1 and 2. If not, re-render.
"""
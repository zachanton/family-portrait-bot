# aiogram_bot_template/services/prompting/styles/photoshoot_continuation.py

PROMPT_PHOTOSHOOT_CONTINUATION = """
**GOAL:** Generate the **next frame** in a photoshoot sequence. You must **preserve the subjects' identities and the overall style** from the reference image, but apply the new **pose and composition** commands below.

**HARD CONSTRAINTS**

*   **REFERENCE IMAGE IS LAW FOR IDENTITY & STYLE:** Replicate the faces, skin texture, hair, and the established lighting, color, and background style from the provided image.
*   **DO NOT CHANGE FACES, PEOPLE, HANDS, OR LOGOS** from the established identity.
*   Strictly photorealistic.
*   Full-bleed output as defined in the original style prompt. No borders, frames, etc.
*   Exactly two people visible.

---
**IDENTITY LOCK DATA (NON-NEGOTIABLE)**
{{IDENTITY_LOCK_DATA}}
---

---
**NEW FRAME INSTRUCTIONS (APPLY THESE CHANGES)**
{{POSE_AND_COMPOSITION_DATA}}
---

**STEP-BY-STEP ACTIONS**

1.  **Analyze Reference Image:** Lock onto the identities, lighting setup, color grading, and background texture.
2.  **Apply New Instructions:** Modify the subjects' poses, expressions, and the camera framing according to the "NEW FRAME INSTRUCTIONS".
3.  **Synthesize:** Render the new frame, ensuring a seamless blend of established identity/style with the new composition. The output should look like the very next picture taken in the same photoshoot.
4.  **Retouch & Crop:** Perform subtle, realistic retouching and crop to 4:5 vertical head-and-shoulders, as per the original style's rules.

**OUTPUT**

*   One PNG, 1536×1920 (4:5), full-bleed, adhering to the original style's output constraints.
"""
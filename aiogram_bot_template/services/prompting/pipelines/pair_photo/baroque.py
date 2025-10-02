PROMPT_BAROQUE = """
GOAL: Produce an advertising-grade couple portrait in a Baroque chiaroscuro aesthetic (Caravaggio-like lighting) — dramatic warm side key, deep shadows, near-black umber backdrop, edge-to-edge, both subjects looking at the camera.

HARD CONSTRAINTS
* Edit the provided pixels only for identity; do not create/replace people, hands, text, or logos.
* Wardrobe & hair restyling to a restrained Baroque-inspired look IS ALLOWED.
* Strictly photorealistic (photographic realism).
* Full-bleed output: fill the canvas to every edge with image content. No borders, frames, soft ovals, added vignettes, paper textures, stickers, watermarks, or transparency.
* Exactly two people visible; no duplicates or mirrored copies.

{{IDENTITY_LOCK_DATA}}

STYLE TARGET — “Baroque Chiaroscuro (Caravaggio-like)”
* Background: near-black umber/brown with very subtle warm falloff; no visible texture/brushstroke overlays; 100% opaque to every edge; no props.
* Lighting: single warm key from camera-left at ~35–45° and slightly above eye level; strong light falloff across faces; clear Rembrandt triangle on the shadow cheek; very gentle fill from camera-right (minimal); optional faint hair/kicker to separate from background; natural, NOT an added vignette.
* Tonality: low saturation overall (skin remains natural), deep shadows with preserved detail (no crushed blacks), smooth highlight roll-off; punchy but clean contrast; no HDR halos, no teal–orange.
* Texture: preserve pores, hair sheen, fabric weave; do NOT add paper grain, scratches, or painterly overlays.

WARDROBE & GROOMING (allowed changes)
* Woman: hair in a neat bun/low updo or soft waves pulled back; dark matte or deep jewel-tone dress/blouse with modest neckline; optional small pearl/brooch; no modern logos.
* Man: dark matte jacket/coat or simple suit silhouette; high-collar/plain shirt; optional subtle cravat-like fold; hair neatly combed; no modern logos.
* Palette: black, charcoal, deep brown, forest green, burgundy, ivory accents; matte textures preferred; minimal metallics.

STEP-BY-STEP ACTIONS
1. Remove all feathered mattes/ovals and any drop shadows around cutouts.
2. Background: extend/replace with a continuous near-black umber backdrop; edge-to-edge opacity; clean hair edges (no halos); no decorative gradients or frames.
3. Lighting pass: apply a warm key from camera-left with steep falloff; gentle minimal fill on camera-right; optional faint hair light only for separation; ensure a readable Rembrandt triangle and natural catchlights.
4. Wardrobe & hair restyle per rules above; ensure fabric folds/speculars match the key direction; remove modern straps/buckles/logos.
5. Recompose (move/scale/rotate/warp only): place subjects cheek-to-temple and shoulder-to-shoulder; woman slightly in front/left, man behind/right; ~12% overlap for natural occlusion; align eye lines; slight inward head tilt (~5°).
6. Eye-contact correction: both subjects should look at the camera; if needed, nudge the iris position ONLY (see Identity Lock) while preserving eyelids, catchlights, and proportions.
7. Crop: 4:5 vertical, head-and-shoulders above the collarbones (no elbows/torsos).
8. Grading: warm bias in highlights/midtones (subtle), deep clean shadows; gentle S-curve; maintain skin micro-texture; avoid banding; do NOT add artificial vignettes or paper textures.
9. Retouch (subtle, realistic): tame glare/noise; mild local contrast/sharpness (eyes, hair edges); keep all identity anchors unchanged.

OUTPUT
* One PNG, 1536×1920 (4:5), full-bleed with no vignettes/ovals/overlays.
* If any matte/vignette remains, remove it and refill with the near-black umber background so the image is edge-to-edge.
"""

PROMPT_BAROQUE_NEXT_SHOT = """
GOAL: Produce the next shot in a photoshoot, creating a new pose while maintaining the established Baroque Chiaroscuro aesthetic, wardrobe, and absolute facial identity.

REFERENCE IMAGES
*   **Input 1 (Composite Photo):** THE ABSOLUTE SOURCE OF TRUTH FOR FACIAL IDENTITY. Faces must match this photo exactly.
*   **Input 2 (Previous Shot):** THE ABSOLUTE SOURCE OF TRUTH FOR STYLE. Match the lighting, color grading, background, wardrobe, and hair from this image.

HARD CONSTRAINTS
*   Facial identity, age, and proportions must be taken **exclusively** from **Input 1 (Composite Photo)**.
*   The overall aesthetic (lighting, color, background, wardrobe, hair) must be taken **exclusively** from **Input 2 (Previous Shot)**.
*   Strictly photorealistic.
*   Full-bleed output. No borders, frames, vignettes, or overlays.
*   Exactly two people visible.

{{IDENTITY_LOCK_DATA}}

STEP-BY-STEP ACTIONS
1.  **Identity Transfer:** Analyze **Input 1 (Composite)** and apply the facial features, structure, and unique details described in the IDENTITY_LOCK_DATA section to the new pose.
2.  **Style Transfer:** Analyze **Input 2 (Previous Shot)** and replicate its Baroque chiaroscuro lighting, warm tonality, umber background, and specific wardrobe/hair styling.
3.  **New Pose & Composition:** Execute the new pose and composition as described below.
    {{POSE_AND_COMPOSITION_DATA}}
4.  **Integration & Refinement:** Seamlessly blend the identity from Input 1 with the style from Input 2 into the new pose. Ensure light and shadow interact correctly with the new facial angles. Perform subtle, realistic retouching.

OUTPUT
*   One PNG, 1536×1920 (4:5), full-bleed, representing the next shot in the sequence.
"""
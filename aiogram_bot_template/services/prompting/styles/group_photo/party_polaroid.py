PROMPT_PARTY_POLAROID = """
GOAL: Produce a candid party photo that looks like it was shot on a Polaroid instant camera: soft flash lighting, a relaxed moment, authentic white Polaroid frame, two subjects primarily in focus.

HARD CONSTRAINTS
* Edit the provided pixels only for faces/identity; do not create/replace people, hands, text, or logos.
* Wardrobe & hair restyling to casual party attire IS ALLOWED.
* Photorealistic instant-film aesthetic (not a painting or vector).
* Exactly two people visibly recognizable in the image; no duplicates or mirrored copies; no other recognizable faces in the background.
* Include an authentic **white Polaroid frame** (thicker bottom border). No stickers, watermarks, brand text, or handwriting on the frame.

{{IDENTITY_LOCK_DATA}}

STYLE TARGET — “Candid party Polaroid”
* Look & tone: instant-film color response (slight warm/magenta bias, subdued saturation), noticeable but fine film grain, gentle highlight halation around bright bulbs, natural light falloff.
* Lighting: **soft, flattering flash from slightly above the lens as key**; ambient warm tungsten/string lights in the background.
* Background: indoor party environment with soft bokeh of fairy lights/garlands, balloons/cups as shapes; **no readable logos, no recognizable extra faces** (silhouettes/bokeh only).
* Composition vibe: spontaneous but well-framed, natural half-smiles.

WARDROBE & GROOMING (allowed changes)
* Convert visible modern/neutral clothing to casual party wear without logos: 
  - Woman: hair down or loose up-do; simple dress or blouse; subtle jewelry kept in same pierce position.
  - Man: casual shirt/tee or light jacket; clean grooming; no bare shoulders.
* Colors: friendly warm palette; avoid neon clipping.

STEP-BY-STEP ACTIONS
1. Remove any feathered mattes/ovals and drop shadows around cutouts.
2. Background: replace/extend with an **indoor party** scene (string lights, warm ambient), shallow depth of field; **100% opaque to every edge inside the Polaroid image area**; clean hair edges (no halos).
3. Wardrobe & hair restyle per rules above; ensure fabric folds/speculars match the flash lighting; keep jewelry positions.
4. Eye-contact correction: if a gaze is off-camera, nudge the **iris position only** per Identity Lock.
5. Recompose (move/scale/rotate/warp only): **classic portrait framing, head-and-shoulders or upper bust**; place subjects cheek-to-temple, shoulder-to-shoulder with natural overlap (~12%); align eye lines; slight inward head tilt (~5°). **Lens equivalent feel of 85-135mm** for flattering compression and separation from the background.
6. Insert **classic Polaroid frame**: white, with bottom border ~2× thicker than sides; frame edges crisp; no external shadows, stickers, or text.
7. Film look grading: warm flash tonality, gentle S-curve contrast; preserve skin micro-texture; add fine grain and mild halation only; avoid heavy filters/HDR, avoid teal-orange.
8. Retouch subtle: reduce harsh glare/noise if needed; mild local contrast/sharpness; keep all identity anchors unchanged.

OUTPUT
* One PNG, **2048×2496** (approx Polaroid aspect with frame), portrait orientation.
* The Polaroid frame is part of the image; inside the frame, fill edge-to-edge with the party scene (no gray/transparent areas).
"""
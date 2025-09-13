PROMPT_PARTY_POLAROID = """
GOAL: Produce a candid party photo that looks like it was shot on a Polaroid instant camera: on-camera flash, casual moment, authentic white Polaroid frame, two subjects primarily in focus.

HARD CONSTRAINTS
* Edit the provided pixels only for faces/identity; do not create/replace people, hands, text, or logos.
* Wardrobe & hair restyling to casual party attire IS ALLOWED.
* Photorealistic instant-film aesthetic (not a painting or vector).
* Exactly two people visibly recognizable in the image; no duplicates or mirrored copies; no other recognizable faces in the background.
* Include an authentic **white Polaroid frame** (thicker bottom border). No stickers, watermarks, brand text, or handwriting on the frame.

IDENTITY LOCK (must match the source)
* Keep face width and jaw/chin geometry; do not slim or reshape faces.
* Preserve inter-pupillary distance, eyelid shapes and eye aperture; only minimal iris re-positioning for eye contact (≤ 10% of iris diameter, no redraw).
* Keep eyebrow thickness/angle, nose bridge & tip shape, lip fullness & natural corner asymmetry.
* Preserve skin micro-texture (freckles/pores/stubble); no beauty smoothing.
* Keep ear shape and earring pierce positions; jewelry may be simplified but not relocated.

STYLE TARGET — “Candid party Polaroid”
* Look & tone: instant-film color response (slight warm/magenta bias, subdued saturation), noticeable but fine film grain, gentle highlight halation around bright bulbs and cups, mild flash falloff/vignetting from the lens (natural only).
* Lighting: direct **on-camera flash** as key; ambient warm tungsten/string lights in the background.
* Background: indoor party environment with soft bokeh of fairy lights/garlands, balloons/cups as shapes; **no readable logos, no recognizable extra faces** (silhouettes/bokeh only).
* Composition vibe: spontaneous, slightly off-center framing, tiny hand-held tilt allowed (≤ 3°); natural half-smiles.

WARDROBE & GROOMING (allowed changes)
* Convert visible modern/neutral clothing to casual party wear without logos: 
  - Woman: hair down or loose up-do; simple dress or blouse; subtle jewelry kept in same pierce position.
  - Man: casual shirt/tee or light jacket; clean grooming; no bare shoulders.
* Colors: friendly warm palette; avoid neon clipping.

STEP-BY-STEP ACTIONS
1. Remove any feathered mattes/ovals and drop shadows around cutouts.
2. Background: replace/extend with an **indoor party** scene (string lights, warm ambient), shallow depth of field; **100% opaque to every edge inside the Polaroid image area**; clean hair edges (no halos).
3. Wardrobe & hair restyle per rules above; ensure fabric folds/speculars match the flash lighting; keep jewelry positions.
4. Recompose (move/scale/rotate/warp only): tight two-shot, chest-up; light casual lean-in; slight overlap (~12%) for natural occlusion; camera at eye level; 35–45 mm equivalent feel.
5. Gaze (candid): at least one subject looking at camera; the other may glance slightly off-lens (≤ 10°). If needed, nudge **iris position only** per Identity Lock.
6. Insert **classic Polaroid frame**: white, with bottom border ~2× thicker than sides; frame edges crisp; no external shadows, stickers, or text.
7. Film look grading: warm flash tonality, gentle S-curve contrast; preserve skin micro-texture; add fine grain and mild halation only; avoid heavy filters/HDR, avoid teal-orange.
8. Retouch subtle: reduce harsh glare/noise if needed; mild local contrast/sharpness; keep all identity anchors unchanged.

OUTPUT
* One PNG, **2048×2496** (approx Polaroid aspect with frame), portrait orientation.
* The Polaroid frame is part of the image; inside the frame, fill edge-to-edge with the party scene (no gray/transparent areas).
"""
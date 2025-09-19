PROMPT_RETRO_MOTEL = """
GOAL: Produce an advertising-grade couple portrait in a Retro Motel 1950s Pastel aesthetic — pastel motel backdrop with geometric shadows, late-afternoon hard sun with soft bounce, edge-to-edge background, both subjects looking at the camera.

HARD CONSTRAINTS
* Edit the provided pixels only for identity; do not create/replace people, hands, text, or logos.
* Wardrobe & hair restyling to a mid-century 1950s look IS ALLOWED.
* Strictly photorealistic (photographic realism).
* Full-bleed output: fill the canvas to every edge with image content. No borders, frames, soft ovals, added vignettes, stickers, watermarks, paper textures, or transparency.
* Exactly two people visible; no duplicates or mirrored copies; no other recognizable faces in the background.

{{IDENTITY_LOCK_DATA}}

STYLE TARGET — “Retro Motel 1950s Pastel”
* Background: pastel motel vibe — painted stucco or tiled wall in mint/salmon/robin’s-egg/butter-cream; allow crisp geometric shadows from venetian blinds or signage edges on the background only. No readable signage or brand marks. 100% opaque to every edge.
* Lighting: hard late-afternoon sun as key (directional, defined shadow edges) + soft warm bounce from the opposite side for pleasing skin; optional faint hair/separation light; clean round catchlights; avoid HDR halos.
* Tonality: gentle pastel palette with medium contrast; warm bias; highlights clean, blacks not crushed; avoid neon clipping and banding.
* Texture: preserve natural skin pores, hair detail, and fabric weave; do NOT add paper textures or film scratches.

WARDROBE & GROOMING (allowed changes)
* Woman: mid-century hair (soft set waves, neat ponytail with scarf, or pinned sides); short-sleeve blouse or simple dress with modest neckline; optional small pearl studs; no logos.
* Man: 1950s camp-collar shirt (solid or simple stripe), or lightweight jacket; neatly combed hair; optional cuff roll; no logos.
* Palette: soft pastels and creams; small contrasting accents allowed; avoid modern prints and brand marks.

STEP-BY-STEP ACTIONS
1. Remove all feathered mattes/ovals and any drop shadows around cutouts.
2. Background: extend/replace with a continuous pastel motel backdrop; add crisp, scene-motivated geometric shadow patterns (venetian blinds/signage) on the background. Ensure edge-to-edge opacity and clean hair edges (no halos).
3. Lighting pass: apply hard key from late-afternoon sun with soft warm bounce fill; keep faces well-exposed; maintain natural catchlights; avoid harsh cast shadows across eyes and key facial features.
4. Wardrobe & hair restyle per the 1950s rules above; match fabric sheen/folds and hair highlights to light direction; remove modern straps/buckles/logos.
5. Recompose (move/scale/rotate/warp only): cheek-to-temple, shoulder-to-shoulder; woman slightly in front/left, man behind/right; ~12% overlap; align eye lines; slight inward head tilt (~5°). Lens feel ~50–85 mm equivalent.
6. Eye-contact correction: both subjects should look at the camera; if needed, nudge the iris position ONLY (see Identity Lock) while preserving eyelids, catchlights, and proportions.
7. Crop: 4:5 vertical, head-and-shoulders above the collarbones (no elbows/torsos).
8. Grading: warm editorial WB; medium contrast with pastel saturation; preserve highlight roll-off and avoid banding on smooth pastel areas; maintain skin micro-texture; no teal–orange LUTs, no artificial vignettes.
9. Retouch (subtle, realistic): reduce glare/noise; mild local contrast/sharpness (eyes, hair sheen); keep all identity anchors unchanged.

OUTPUT
* One PNG, 1536×1920 (4:5), full-bleed with no vignettes/ovals/overlays.
* If any matte/vignette remains, remove it and refill with the pastel motel background so the image is edge-to-edge.
"""
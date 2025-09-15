PROMPT_VOGUE = """
GOAL: Produce an advertising-grade couple portrait in a Vogue-style high-key editorial aesthetic — clean seamless white background, soft wraparound light, both subjects looking at the camera.

HARD CONSTRAINTS
* Edit the provided pixels only for identity; do not create/replace people, hands, text, or logos.
* Wardrobe & hair restyling to a modern high-fashion editorial look IS ALLOWED.
* Strictly photorealistic (photographic realism).
* Full-bleed output: fill the canvas to every edge with image content. No borders, frames, soft ovals, vignettes, stickers, watermarks, or transparency.
* Exactly two people visible; no duplicates or mirrored copies.

{{IDENTITY_LOCK_DATA}}

STYLE TARGET — “Vogue High-Key Editorial”
* Background: seamless studio white (pure but not matte; allow subtle natural falloff/contact shadow), 100% opaque to every edge; no props.
* Lighting: soft wraparound clamshell (key slightly above lens + soft fill from below); large diffused sources; minimal, clean shadows; optional very soft hair light for separation; symmetrical round catchlights.
* Tonality & color: neutral white balance (slight cool editorial bias allowed); clean highlights with controlled roll-off; medium contrast; no HDR halos, no color cast on skin.
* Texture: preserve natural skin pores and fabric detail; no paper textures, scratches, or artificial vignettes.

WARDROBE & GROOMING (allowed changes)
* Woman: sleek editorial hair (low bun/ponytail or polished waves); modern chic outfit in black/white/cream (tailored blazer, structured blouse, satin top); minimal jewelry (studs/pearl); no logos or busy prints.
* Man: tailored suit or minimalist jacket/tee combo; matte or slightly glossy lapels; neat grooming; no logos.
* Palette: monochrome/neutrals (white, black, cream, gray); subtle metallic accents allowed.

STEP-BY-STEP ACTIONS
1. Remove all feathered mattes/ovals and any drop shadows around cutouts.
2. Background: extend/replace with a continuous seamless studio white; ensure edge-to-edge opacity; keep hair edges clean (no halos). Allow a faint natural contact shadow behind heads/shoulders (lighting only).
3. Lighting pass: apply soft clamshell setup for even, flattering illumination; avoid hard edges; ensure catchlights near 11–1 o’clock; add very soft hair/back separation if needed.
4. Wardrobe & hair restyle per rules above; align fabric sheen and folds with light direction; remove modern straps/buckles/logos.
5. Recompose (move/scale/rotate/warp only): place subjects cheek-to-temple and shoulder-to-shoulder; woman slightly in front/left, man behind/right; ~12% overlap; align eye lines; slight inward head tilt (~5°).
6. Eye-contact correction: both subjects should look at the camera; if needed, nudge the iris position ONLY (see Identity Lock) while preserving eyelids and proportions.
7. Crop: 4:5 vertical, head-and-shoulders above the collarbones (no elbows/torsos).
8. Editorial grading: neutral WB with crisp whites; medium contrast; preserve highlight detail; avoid banding in white areas; maintain skin micro-texture; no teal–orange, no heavy LUTs.
9. Retouch (subtle, realistic): reduce glare/noise; mild local contrast/sharpness focusing on eyes, lashes, hair sheen; keep all identity anchors unchanged.

OUTPUT
* One PNG, 1536×1920 (4:5), full-bleed with no vignettes/ovals/overlays.
* If any matte/vignette remains, remove it and refill with seamless white so the image is edge-to-edge.
"""
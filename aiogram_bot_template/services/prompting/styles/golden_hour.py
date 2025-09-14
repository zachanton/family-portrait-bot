PROMPT_GOLDEN_HOUR = """
GOAL: Produce an advertising-grade couple portrait in a warm “Golden Hour Backlit Haze” aesthetic — sunlit back rim light, airy haze, soft front fill, edge-to-edge background, both subjects looking at the camera.

HARD CONSTRAINTS
* Edit the provided pixels only for identity; do not create/replace people, hands, text, or logos.
* Wardrobe & hair restyling to a modern outdoor golden-hour look IS ALLOWED.
* Strictly photorealistic (photographic realism).
* Full-bleed output: fill the canvas to every edge with image content. No borders, frames, soft ovals, added vignettes, stickers, watermarks, paper textures, or transparency.
* Exactly two people visible; no duplicates or mirrored copies; no other recognizable faces in the background.

{{IDENTITY_LOCK_DATA}}

STYLE TARGET — “Backlit Golden Hour”
* Background: outdoor nature scene (sunlit foliage/meadow/coastline) with shallow depth of field; creamy bokeh; authentic atmospheric haze. Background must be 100% opaque to every edge; no props with branding.
* Lighting: the sun acts as a warm back/rim light behind or just off to the side of the subjects; apply soft front fill (sky/bounce) to keep faces well-exposed; subtle lens flare/bloom permitted if naturally motivated (no graphic overlays).
* Tonality: warm golden/amber bias; pastel saturation; gentle S-curve contrast with smooth highlight roll-off; avoid HDR halos and color banding.
* Color hygiene: keep skin tones believable—warm, not orange; preserve whites in eyes/teeth; avoid teal–orange LUTs.
* Texture: maintain natural skin pores and hair detail; no film scratches, paper grain, or added vignette.

WARDROBE & GROOMING (allowed changes)
* Woman: light, flowy fabrics (linen/cotton/silk); soft hair with slight wind lift; minimal jewelry kept in same pierce position; no logos.
* Man: casual refined (light shirt/tee, knit, or unstructured jacket); matte textures that catch rim light; neat grooming; no logos.
* Palette: earth tones and creams (ivory, sand, sage, dusty rose) that glow under backlight.

STEP-BY-STEP ACTIONS
1. Remove all feathered mattes/ovals and any drop shadows around cutouts.
2. Background: extend/replace with a continuous outdoor scene appropriate for golden hour; ensure edge-to-edge opacity; clean hair edges (no halos).
3. Lighting pass: position a warm back/rim light to create halo on hair/shoulders; add soft front fill for readable faces; allow subtle natural flare/haze; keep catchlights intact.
4. Wardrobe & hair restyle per rules above; align fabric folds and sheen with the light direction; remove modern straps/buckles/logos.
5. Recompose (move/scale/rotate/warp only): cheek-to-temple, shoulder-to-shoulder; woman slightly in front/left, man behind/right; ~12% overlap; align eye lines; slight inward head tilt (~5°). Lens feel ~85–105mm equivalent.
6. Eye-contact correction: both subjects should look at the camera; if needed, nudge the iris position ONLY (see Identity Lock) while preserving eyelids, catchlights, and proportions.
7. Crop: 4:5 vertical, head-and-shoulders above the collarbones (no elbows/torsos).
8. Grading: warm golden WB; pastel saturation; gentle S-curve; preserve highlight detail; avoid banding in sky/bokeh and avoid HDR halos; maintain skin micro-texture.
9. Retouch (subtle, realistic): tame glare/noise; mild local contrast/sharpness (eyes, lashes, hair edges); keep all identity anchors unchanged.

OUTPUT
* One PNG, 1536×1920 (4:5), full-bleed with no vignettes/ovals/overlays.
* If any matte/vignette remains, remove it and refill with the natural outdoor background so the image is edge-to-edge.
"""
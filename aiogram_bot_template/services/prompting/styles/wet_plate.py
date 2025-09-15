PROMPT_WET_PLATE = """
GOAL: Produce an advertising-grade couple portrait in a “Wet-Plate Collodion Tonality (tintype-inspired)” aesthetic — cool silver monochrome, emphasized micro-contrast, soft single-key lighting, edge-to-edge background, both subjects looking at the camera.

HARD CONSTRAINTS
* Edit the provided pixels only for identity; do not create/replace people, hands, text, or logos.
* Wardrobe & hair restyling to a restrained, period-agnostic dark look IS ALLOWED.
* Strictly photorealistic (photographic realism).
* Full-bleed output: fill the canvas to every edge with image content. No borders, frames, soft ovals, added vignettes, paper textures, scratches, plate edges, stickers, watermarks, stains, or transparency.
* Exactly two people visible; no duplicates or mirrored copies; no other recognizable faces in the background.

{{IDENTITY_LOCK_DATA}}

STYLE TARGET — “Wet-Plate Collodion Tonality (Tintype-Inspired)”
* Monochrome tonality: cool, silvery highlights and slightly cooler shadows; rich midtones; fine film-like grain. No sepia or brown tinting.
* Spectral response emulation: ortho/early-pan look — reds render slightly darker, lighter response to blue; apply channel mix accordingly while keeping skin believable.
* Background: matte, near-black dark gray/umber seamless with very subtle natural falloff; 100% opaque to every edge; no decorative textures, borders, or vignettes; no props.
* Lighting: single soft key from camera-left at ~35–45° and slightly above eye level; minimal soft fill from camera-right; optional faint hair/kicker just for separation; clear modeling with smooth highlight roll-off; natural catchlights.
* Optics: shallow depth of field; background softly defocused; an extremely subtle edge “swirl” in far bokeh is acceptable but avoid smeary or artificial distortion.

WARDROBE & GROOMING (allowed changes)
* Woman: neat bun/low updo or restrained waves pulled back; dark matte blouse/dress with modest neckline; optional small pearl/stud; no logos or modern prints.
* Man: dark matte jacket/coat or simple suit silhouette; plain high-collar or band-collar shirt; neatly combed hair; no logos.
* Palette (pre-conversion): deep neutrals and earth tones that translate well to monochrome; minimal gloss.

STEP-BY-STEP ACTIONS
1. Remove all feathered mattes/ovals and any drop shadows around cutouts.
2. Background: extend/replace with a continuous matte dark seamless (near-black gray/umber); edge-to-edge opacity; clean hair edges (no halos), no decorative gradients or frames.
3. Lighting pass: apply a soft key from camera-left with pronounced falloff; minimal fill on camera-right; optional faint hair/kicker for separation; ensure natural catchlights and readable facial form.
4. Wardrobe & hair restyle per rules above; align fabric folds and sheen with the light direction; remove modern straps/buckles/logos.
5. Recompose (move/scale/rotate/warp only): cheek-to-temple and shoulder-to-shoulder; woman slightly in front/left, man behind/right; ~12% overlap for natural occlusion; align eye lines; slight inward head tilt (~5°).
6. Eye-contact correction: both subjects should look at the camera; if needed, nudge the iris position ONLY (see Identity Lock) while preserving eyelids, catchlights, and proportions.
7. Crop: 4:5 vertical, head-and-shoulders above the collarbones (no elbows/torsos).
8. Monochrome grading (collodion-inspired): convert to B&W with cool silver tonality, rich midtones, deep but not crushed blacks; emphasize micro-contrast; add fine film-like grain only; NO added borders, vignettes, paper/plate textures, scratches, chemical streaks, or dust.
9. Retouch (subtle, realistic): tame glare/noise; mild local contrast/sharpness to emphasize eyes and hair edges; keep all identity anchors unchanged.

OUTPUT
* One PNG, 1536×1920 (4:5), full-bleed with no vignettes/ovals/overlays.
* If any matte/vignette remains, remove it and refill with the matte dark background so the image is edge-to-edge.
"""
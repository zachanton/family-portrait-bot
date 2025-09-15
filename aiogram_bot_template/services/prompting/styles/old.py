PROMPT_OLD = """
GOAL: Produce an advertising-grade couple family portrait in a late-19th-century studio-portrait aesthetic, with an edge-to-edge background and both subjects looking at the camera.

HARD CONSTRAINTS
* Edit the provided pixels only. Do not create/replace faces, people, hands, text, or logos.
* Wardrobe & hair restyling to a historically plausible 19th-century studio look IS ALLOWED.
* Strictly photorealistic (photographic realism).
* Full-bleed output: fill the canvas to every edge with image content. No borders, frames, soft ovals, vignettes, flat gray/white panels, gradients, stickers, watermarks, or transparency.
* Exactly two people visible; no duplicates or mirrored copies.

{{IDENTITY_LOCK_DATA}}

STYLE TARGET — “Classic 19th-century studio portrait”
* Background: hand-painted studio backdrop typical of the era (mottled, brushy), deep umber/olive/brown with subtle warm gradient; no props.
* Lighting: soft window key from camera-left with gentle falloff and a mild Rembrandt triangle on the shadow cheek; soft fill from camera-right.
* Tonality: warm golden/amber bias with subtle albumen/sepia cast; low–medium saturation; gentle S-curve contrast; blacks not crushed, highlights not clipped.
* Texture: keep natural skin micro-texture; do NOT add paper grain, scratches, borders, or vignette.

WARDROBE & GROOMING RULES (allowed changes)
* Replace modern clothing/straps with period-appropriate garments.
  - Woman: hair in a neat 19th-century updo/bun or center-part with pinned sides; high-neck lace or embroidered blouse/dress with modest neckline; optional small pearl earrings or a subtle brooch at the collar; natural fabrics (cotton/linen/silk), no modern logos.
  - Man: neatly combed side-part; dark wool suit or frock-coat silhouette with waistcoat and high-collar shirt; optional simple cravat or narrow bow; no bare shoulders.
* Colors: deep neutrals (black, charcoal, sepia brown, forest green, cream, ivory). Avoid bright synthetic hues and glossy synthetics.
* Keep body proportions and shoulder widths; do not alter physique.

STEP-BY-STEP ACTIONS
1. Remove all feathered mattes/ovals and any drop shadows around cutouts.
2. Background: extend/replace the background ONLY with a continuous hand-painted 19th-century studio backdrop (mottled umber/olive/brown), shallow depth of field. Background must be 100% opaque and continuous to every edge; clean hair edges (no halos).
3. Wardrobe & hair restyle: convert visible modern apparel and hairstyles to the period-accurate versions (see rules above) while keeping earrings position; remove modern straps/buckles. Ensure garment edges, folds, and fabric sheen match the new lighting.
4. Recompose (move/scale/rotate/warp only): place subjects cheek-to-temple and shoulder-to-shoulder; woman slightly in front/left, man behind/right; ~12% overlap for natural occlusion; align eye lines; slight inward head tilt (~5°).
5. Eye-contact correction: if a gaze is off-camera, nudge the iris position ONLY (see Identity Lock) while preserving eyelids, catchlights, color, and proportions.
6. Crop: 4:5 vertical, head-and-shoulders above the collarbones (no elbows/torsos).
7. Color & light unification for the 19th-century look: warm window key, subdued saturation, gentle S-curve contrast; NO HDR halos/filters; NO modern teal-orange; preserve skin micro-texture.
8. Retouch (subtle, realistic): reduce glare/noise; mild local contrast/sharpness; keep all identity anchors unchanged.

OUTPUT
* One PNG, 1536×1920 (4:5), full-bleed with no vignettes/ovals/overlays.
* If any matte/vignette remains, remove it and refill with the painted studio background so the image is edge-to-edge.
"""
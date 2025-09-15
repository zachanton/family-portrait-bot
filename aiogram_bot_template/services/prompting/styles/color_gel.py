PROMPT_COLOR_GEL = """
GOAL: Produce an advertising-grade couple portrait in a bold 1980s color-gel studio aesthetic — saturated crossed gels, glossy highlights, edge-to-edge background, both subjects looking at the camera.

HARD CONSTRAINTS
* Edit the provided pixels only for identity; do not create/replace people, hands, text, or logos.
* Wardrobe & hair restyling to a period-accurate 1980s look IS ALLOWED.
* Strictly photorealistic (photographic realism).
* Full-bleed output: fill the canvas to every edge with image content. No borders, frames, soft ovals, vignettes, flat gray/white panels, gradients, stickers, watermarks, or transparency.
* Exactly two people visible; no duplicates or mirrored copies.

{{IDENTITY_LOCK_DATA}}

STYLE TARGET — “1980s Color-Gel Studio Portrait”
* Background: seamless studio backdrop with crossed color gels (magenta vs. cyan/blue) forming a smooth, saturated gradient; no props; 100% opaque to every edge.
* Lighting: neutral beauty-dish key from camera-front to keep natural skin tone; strong magenta gel from camera-left and cyan/blue gel from camera-right as opposing rims; optional subtle hair light; visible color bleed on hair and shoulders; crisp round catchlights.
* Tonality: high saturation with clean highlights and deep shadows; punchy contrast without HDR halos or clipping; fine, minimal grain; glossy speculars on hair/fabric.
* Color hygiene: keep skin believable—let gels tint edges/rims, not turn mid-face green/blue.

WARDROBE & GROOMING (allowed changes)
* Woman: voluminous 80s blowout or soft teased waves; statement earrings; satin/sequin/lamé top or structured blouse with slight shoulder emphasis; bold but credible shine; no logos.
* Man: neatly styled side-part or wet-look; dark jacket or suit with glossy lapels / leather jacket vibe; optional slim tie; shirt with simple pattern or solid; no logos.
* Palette: saturated jewel tones (magenta, cyan, purple, electric blue, black); metallic accents allowed; avoid brand marks.

STEP-BY-STEP ACTIONS
1. Remove all feathered mattes/ovals and any drop shadows around cutouts.
2. Background: extend/replace with a continuous seamless backdrop lit by crossed magenta/cyan gels; edge-to-edge opacity; clean hair edges (no halos).
3. Lighting pass: maintain neutral key on faces; add colored rim spill from left/right; ensure natural skin midtones, with gel influence mainly on contours and shoulders.
4. Wardrobe & hair restyle to the 1980s rules above; match fabric sheen and folds to the light directions; remove modern straps/buckles/logos.
5. Recompose (move/scale/rotate/warp only): cheek-to-temple and shoulder-to-shoulder; woman slightly in front/left, man behind/right; ~12% overlap; align eye lines; slight inward head tilt (~5°).
6. Eye-contact correction: if a gaze is off-camera, nudge the iris position ONLY (see Identity Lock) while preserving eyelids, catchlights, and proportions.
7. Crop: 4:5 vertical, head-and-shoulders above the collarbones (no elbows/torsos).
8. Color & contrast: vivid saturation, punchy contrast; clean highlights; no teal–orange LUTs, no HDR halos; preserve skin micro-texture and avoid banding on the backdrop gradient.
9. Retouch (subtle, realistic): reduce glare/noise where needed; mild local contrast/sharpness (eyes, hair sheen); keep all identity anchors unchanged.

OUTPUT
* One PNG, 1536×1920 (4:5), full-bleed with no vignettes/ovals/overlays.
* If any matte/vignette remains, remove it and refill with the gel-lit seamless so the image is edge-to-edge.
"""
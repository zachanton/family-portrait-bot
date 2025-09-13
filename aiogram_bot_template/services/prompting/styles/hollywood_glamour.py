PROMPT_HOLLYWOOD_GLAMOUR = """
GOAL: Produce an advertising-grade couple portrait in a 1930s Hollywood Glamour aesthetic — pure black-and-white, crisp studio lighting, edge-to-edge background, both subjects looking at the camera.

HARD CONSTRAINTS
* Edit the provided pixels only for identity; do not create/replace people, hands, text, or logos.
* Wardrobe & hair restyling to a period-accurate 1930s glamour look IS ALLOWED.
* Strictly photorealistic (photographic realism).
* Full-bleed output: fill the canvas to every edge with image content. No borders, frames, soft ovals, vignettes, flat gray/white panels, gradients, stickers, watermarks, or transparency.
* Exactly two people visible; no duplicates or mirrored copies.

IDENTITY LOCK (must match the source)
* Keep face width and jaw/chin geometry; do not slim or reshape faces.
* Preserve inter-pupillary distance, eyelid shapes and eye aperture; only minimal iris re-positioning for eye contact (≤ 10% of iris diameter, no redraw).
* Keep eyebrow thickness/angle, nose bridge & tip shape, lip fullness & natural corner asymmetry.
* Preserve skin micro-texture (freckles/pores/stubble); no beauty smoothing.
* Keep ear shape and earring pierce positions; jewelry may be simplified but not relocated.

STYLE TARGET — “1930s Hollywood Glamour (Black-and-White)”
* Monochrome conversion with rich tonal separation: deep blacks, luminous midtones, clean highlights; fine film-like grain; no color tinting (no sepia).
* Lighting: classic Paramount/butterfly key slightly above and in front of the lens; soft fill from below; subtle hair/kicker rim from behind to separate from the background. Symmetrical butterfly nose shadow; round catchlights near 11–1 o’clock.
* Background: seamless black or very dark gray with gentle falloff; faint halo behind heads only from light, not a vignette; 100% opaque to every edge.
* Contrast/curve: gentle S-curve; no HDR halos; preserve highlight roll-off on cheeks and forehead.

WARDROBE & GROOMING (allowed changes)
* Man: dark tuxedo or deep-charcoal suit (matte or satin lapels), white dress shirt, simple black bow tie; hair neatly side-parted/slicked; no bare shoulders.
* Woman: satin or velvet gown/blouse with elegant neckline (period-appropriate), structured drape; hair in soft 1930s waves or sleek up-do; minimal jewelry (pearls or small stones). No modern logos or prints.

STEP-BY-STEP ACTIONS
1. Remove all feathered mattes/ovals and any drop shadows around cutouts.
2. Background: extend/replace with a continuous dark seamless (black/very dark gray), studio-grade; clean hair edges (no halos); edge-to-edge opacity.
3. Wardrobe & hair restyle per rules above; ensure fabric speculars follow the key light; remove modern straps/buckles.
4. Recompose (move/scale/rotate/warp only): cheek-to-temple and shoulder-to-shoulder; woman slightly in front/left, man behind/right; ~12% overlap; align eye lines; slight inward head tilt (~5°).
5. Eye-contact correction: if a gaze is off-camera, nudge the iris position ONLY (see Identity Lock) while preserving eyelids, catchlights, and proportions.
6. Crop: 4:5 vertical, head-and-shoulders above the collarbones (no elbows/torsos).
7. Monochrome grading: convert to B&W with rich midtones, deep blacks, clean highlights; apply gentle S-curve; add fine film-like grain; NO added frames, paper textures, scratches, or artificial vignettes.
8. Retouch (subtle, realistic): reduce glare/noise; mild local contrast/sharpness to emphasize eyes and hair sheen; keep all identity anchors unchanged.

OUTPUT
* One PNG, 1536×1920 (4:5), full-bleed with no vignettes/ovals/overlays.
* If any matte/vignette remains, remove it and refill with the dark seamless so the image is edge-to-edge.
"""
PROMPT_POP_ART = """
GOAL: Produce an advertising-grade couple portrait in a Pop-Art Color Block (LaChapelle-ish) studio aesthetic — bold saturated color blocks, glossy speculars, edge-to-edge background, both subjects looking at the camera.

HARD CONSTRAINTS
* Edit the provided pixels only for identity; do not create/replace people, hands, text, or logos.
* Wardrobe & hair restyling to a pop-art editorial look IS ALLOWED.
* Strictly photorealistic (photographic realism).
* Full-bleed output: fill the canvas to every edge with image content. No borders, frames, soft ovals, added vignettes, stickers, watermarks, paper textures, or transparency.
* Exactly two people visible; no duplicates or mirrored copies; no other recognizable faces in the background.

IDENTITY LOCK (must match the source)
* Keep face width and jaw/chin geometry; do not slim or reshape faces.
* Preserve inter-pupillary distance, eyelid shapes and eye aperture; only minimal iris re-positioning for eye contact (≤ 10% of iris diameter, no redraw).
* Keep eyebrow thickness/angle, nose bridge & tip shape, lip fullness & natural corner asymmetry.
* Preserve skin micro-texture (freckles/pores/stubble); no beauty smoothing.
* Keep ear shape and earring pierce positions; jewelry may be simplified but not relocated.
* If glasses are present, preserve exact frame geometry (size, rim thickness, lens proportions, nose-pad position).

STYLE TARGET — “Pop-Art Color Block (LaChapelle-ish)”
* Background: seamless studio set with 2–3 large, saturated color blocks (e.g., fuchsia/magenta, cyan/electric blue, lemon yellow). Clean geometric edges; no patterns, no text; 100% opaque to every edge. Allow a subtle real contact shadow behind subjects; no artificial vignettes.
* Lighting: punchy studio look — neutral beauty-dish/softbox key from camera-front to keep natural skin, plus opposing colored rims/fills echoing the background hues (magenta vs. cyan/blue). Add crisp speculars on hair/fabrics; round catchlights near 11–1 o’clock.
* Tonality: high saturation with luminous highlights and deep shadows; strong but clean contrast; avoid clipping and HDR halos; minimal fine grain only.
* Color hygiene: keep skin believable; let color casts live on edges/rims and garments, not mid-face. Preserve whites of eyes/teeth.

WARDROBE & GROOMING (allowed changes)
* Woman: sleek ponytail/bob or polished waves; statement geometric earrings; solid-color dress/top with clean shapes (satin/lamé/vinyl allowed); no logos or text.
* Man: tailored suit or modern jacket/tee combo in saturated solids; optional glossy lapels; neat grooming; no logos.
* Palette: pure primaries and candy neons (magenta, cyan, electric blue, lemon, acid green, black/white accents). Prefer bold solids/color blocking over prints.

STEP-BY-STEP ACTIONS
1. Remove all feathered mattes/ovals and any drop shadows around cutouts.
2. Background: extend/replace with continuous pop-art color blocks (2–3 panels). Ensure edge-to-edge opacity and razor-clean edges; no banding; hair edges clean (no halos).
3. Lighting pass: apply neutral key on faces; add colored rim/spill from left/right to mirror the background palette; optional faint top hair light; keep catchlights crisp.
4. Wardrobe & hair restyle per rules above; align fabric sheen and fold directions with the light; remove modern straps/buckles/logos.
5. Recompose (move/scale/rotate/warp only): cheek-to-temple, shoulder-to-shoulder; woman slightly in front/left, man behind/right; ~12% overlap; align eye lines; slight inward head tilt (~5°). Lens feel ~50–85 mm equivalent.
6. Eye-contact correction: both subjects should look at the camera; if needed, nudge the iris position ONLY (see Identity Lock) while preserving eyelids, catchlights, and proportions.
7. Crop: 4:5 vertical, head-and-shoulders above the collarbones (no elbows/torsos).
8. Color & contrast: vivid saturation and punchy contrast; clean highlight roll-off on skin; prevent banding in large color fields; avoid teal–orange LUTs and heavy filters; maintain skin micro-texture.
9. Retouch (subtle, realistic): tame glare/noise; mild local contrast/sharpness focusing on eyes and hair sheen; keep all identity anchors unchanged.

OUTPUT
* One PNG, 1536×1920 (4:5), full-bleed with no vignettes/ovals/overlays.
* If any matte/vignette remains, remove it and refill with the pop-art color block background so the image is edge-to-edge.
"""
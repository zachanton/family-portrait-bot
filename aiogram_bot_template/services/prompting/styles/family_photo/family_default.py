PROMPT_FAMILY_DEFAULT = """
TASK
Create ONE photorealistic 9:16 full bleed family portrait using ONLY the three attached face images. Do NOT invent, mix, beautify, or “normalize” identities.

IDENTITY MAP
• TOP = MOTHER, MIDDLE = CHILD, BOTTOM = FATHER.

BEHAVE LIKE ID MODULES (emulation)
Act as if you had InstantID / PhotoMaker / ID-Adapter capabilities:
• Build a separate ID embedding for EACH person; inject facial landmarks; decouple ID from non-ID features.
• Maximize internal face-embedding similarity to each reference; if any subject’s similarity is low, REGENERATE. Identity > aesthetics.

MOTHER-FIRST ID LOCK 
• Preserve the MOTHER’s exact facial geometry from her reference, including close-range selfie perspective (do NOT shrink/narrow her nose, cheeks, or jaw; keep natural asymmetry).
• Copy 1:1 landmarks & textures: brow shape/spacing; eye canthus tilt & eyelid crease; iris color/limbal ring; inter-pupil distance; nose bridge/width/alar base/nostrils; philtrum columns; Cupid’s bow & lip volume/commissure angle; nasolabial folds; jaw angle; chin silhouette; ear shape/position.
• Absolutely NO beautification/smoothing/whitening/face-slimming/symmetrization on the MOTHER.

FATHER-FIRST ID LOCK 
• Preserve the FATHER’s exact facial geometry from his reference, including close-range selfie perspective (do NOT shrink/narrow her nose, cheeks, or jaw; keep natural asymmetry).
• Copy 1:1 landmarks & textures: brow shape/spacing; eye canthus tilt & eyelid crease; iris color/limbal ring; inter-pupil distance; nose bridge/width/alar base/nostrils; philtrum columns; Cupid’s bow & lip volume/commissure angle; nasolabial folds; jaw angle; chin silhouette; ear shape/position.
• Absolutely NO beautification/smoothing/whitening/face-slimming/symmetrization on the FATHER.

IDENTITY SEPARATION (avoid leakage)
• Do NOT borrow or average features across people. Keep three distinct identities at all times.

NOT A COLLAGE
• Reconstruct full heads, hairlines, necks, shoulders, upper chest. No floating heads or cut edges.

COMPOSITION & ORDER
• Left→right order: MOTHER — CHILD — FATHER. All THREE fully visible.
• Framing: medium-close **mid-torso and up** (upper arms visible; no tight shoulder crop).
• Camera at eye level; soft, friendly half-smiles.
• Nothing in front of necks/shoulders.

COMPOSITION LOCK — HARD CONSTRAINTS (match the first good example)
Use the following vertical guides with 0% at the **top** edge and 100% at the **bottom** edge of the 9:16 frame. Regenerate until ALL are satisfied:
• **Adults’ eye-lines**: keep BOTH between **24–30%** from the top (slightly above the upper third grid line).
• **Child’s eye-line**: keep between **36–44%** from the top.
• **Headroom cap**: space from the highest hair point to the top frame edge **≤ 3%** of frame height (no big sky above heads).
• **Lower crop**: include **mid-torso**—the bottom frame edge must fall **between 63–72%** from the top (clearly showing torsos).
• **No joint chops**: do **not** crop exactly at elbows or wrists; if cropped, do it well above or below the joint.
• **Reject & regenerate if violated**: if any adult eye-line is **> 32%** or **< 22%** from the top, or if headroom **> 3%**, or if the bottom edge is **above 60%** (people too low) or **below 75%** (too much torso).

PLACEMENT, SCALE & OPTICS
• One consistent perspective, lighting, and white balance across all three.
• Keep all three faces on a similar focal plane to maintain sharpness.

LIGHTING & BACKGROUND — GOLDEN HOUR STYLE
• Time & light: shoot during **golden hour** (first hour after sunrise or last before sunset). Light is **warm, soft, directional** from a low sun.
• Key setup: gentle **backlight or 3/4 backlight** from camera-left to create **natural rim/edge light** on hair and shoulders; avoid harsh flares on faces. Fill with ambient sky or subtle bounce so all three faces are evenly exposed.
• White balance: **warm daylight**; preserve golden tones (no cool cast).
• Background: real outdoor field/park with tall grass or tree line; softly blurred; no bright hotspots crossing faces.
• Consistency: one coherent sunlight direction, shadow falloff, and color across all subjects.

WARDROBE & COLOR PALETTE (match golden hour; no new accessories/haircuts)
• Palette: **soft neutrals + warm earthy accents** (cream, beige, warm white, stone gray, optional sage/rust/terracotta). Avoid neon and stark pure black.

AESTHETIC RECIPE (do not alter identity)
• Camera & lens: **50–65 mm equivalent**; shooting distance **~1.2–1.6 m** for natural perspective and mid-torso framing.
• Aperture: **around f/3.5–f/4.0** to keep all three faces sharp while retaining pleasant golden-hour background blur.
• Composition shape: a subtle **triangle** of heads; adults’ shoulders arc protectively around the child.
• Skin & texture: preserve natural freckles/pores/micro-contrast; no smoothing, whitening, or face-slimming.
• Output finish: crisp hair edges (no halos), even exposure on all faces, no vignettes.

NEGATIVE CONSTRAINTS (must AVOID)
• Missing subjects or >10% occlusion of any face.
• Age/sex changes; new accessories/hats/haircuts.
• CGI/painting/anime/HDR/over-sharpening; skin smoothing; face-slimming; makeup airbrushing.
• Identity blending or cross-person feature transfer.

QUALITY GUARDRAILS (NEGATIVE)
• Forbid: oversized/undersized heads, mismatched head scales, warped glasses, elongated/shortened necks, plastic skin, duplicated/merged features, misaligned eyes, haloing around hair, perspective mismatch between people.
• No extra people, text, logos, watermarks, frames, or borders.
• Reject any image with borders/black bars.

FINAL SELF-CHECK (regenerate until TRUE)
1) The MOTHER is a literal 1:1 match to her reference (geometry, textures, hairline/part, accessories).
2) The FATHER is a literal 1:1 match to his reference (geometry, textures, hairline/part, accessories).
3) The CHILD is a literal 1:1 match to her reference (geometry, textures, hairline/part, accessories).
4) No identity leakage; left→right order is MOTHER — CHILD — FATHER.
5) No borders/black bars; full-bleed output.
6) **Composition lock is satisfied**: adult eye-lines 24–30%; child 36–44%; headroom ≤ 3%; bottom edge at 63–72%; no cropping at elbows/wrists.
7) Final full-bleed image is exactly 9:16.

"""
PROMPT_FAMILY_DEFAULT = """
GOAL
Create ONE photorealistic, full-bleed 9:16 family portrait using ONLY the three attached images. Do NOT invent, blend, beautify, or “normalize” identities.

INPUT LAYOUT (fixed)
• First attached image = MOTHER: contains exactly two portraits of the same person (one front/straight-on, one clean side profile).
• Second attached image = FATHER: contains exactly two portraits of the same person (one front/straight-on, one clean side profile).
• Third attached image = CHILD: contains exactly one front/straight-on portrait.

ASPECT RATIO
• Output must be exactly 9:16 and match the third image’s aspect ratio. Full bleed. No borders/black bars.

IDENTITY PIPELINE (emulation of InstantID / PhotoMaker / ID-Adapter)
• For EACH person, build a separate ID embedding. Adults: fuse front + profile to recover true 3D facial geometry and hairline. Child: use the single front view.
• Inject dense facial landmarks; decouple ID features (geometry, proportions, micro-textures) from non-ID attributes (lighting/background).
• Maximize internal face-embedding similarity to each reference. Targets (cos-sim or equivalent): Mother = 1, Father = 1, Child = 1. If any falls below target, REGENERATE. Identity fidelity > aesthetics.

STRICT ID LOCKS (no beautification)
MOTHER
• Preserve exact facial geometry and natural asymmetry from her references. Do NOT slim face, shrink/narrow nose, or smooth skin.
• Copy 1:1: brow shape/spacing; eye canthus tilt & eyelid crease; iris color/limbal ring; interpupillary distance; nose bridge/width/alar base/nostrils; philtrum; Cupid’s bow & lip volume/commissure angle; nasolabial folds; jaw angle; chin silhouette; ear shape/position; hairline/part, color, and length; freckles/pores/moles and skin tone.

FATHER
• Preserve exact facial geometry and natural asymmetry from his references. Do NOT slim face, shrink/narrow nose, or smooth skin.
• Copy 1:1: brow shape/spacing; eye canthus tilt & eyelid crease; iris color/limbal ring; interpupillary distance; nose bridge/width/alar base/nostrils; philtrum; Cupid’s bow & lip volume/commissure angle; nasolabial folds; jaw angle; chin silhouette; ear shape/position; hairline/part, color, and length; facial hair density/pattern; skin texture and tone.

CHILD
• Preserve exact child facial proportions, features, freckles/pores, hairline/part, color and length. No age change, no makeup or smoothing.

IDENTITY SEPARATION
• Absolutely no borrowing/averaging of features across people. Keep three distinct identities with zero cross-transfer.

NOT A COLLAGE
• Reconstruct full heads, hairlines, necks, shoulders, and upper chest. No floating heads, cut edges, or pasted looks.

COMPOSITION & ORDER (hard)
• Left → right: MOTHER — CHILD — FATHER. All three fully visible.
• Framing: medium-close, mid-torso and up (upper arms visible; no tight shoulder crop).
• Camera at eye level; soft, friendly half-smiles. Nothing occluding necks/shoulders.

COMPOSITION LOCK — NUMERIC CONSTRAINTS (regenerate until all true)
Reference the 9:16 frame with 0% at the top and 100% at the bottom:
• Adults’ eye-lines: BOTH between 24–30% from top.
• Child’s eye-line: 36–44% from top.
• Headroom: ≤ 3% from highest hair point to top edge.
• Lower crop: bottom edge between 63–72% from top (clear mid-torso).
• No joint chops: do not crop exactly at elbows or wrists—crop well above/below.
• Reject & regenerate if any adult eye-line < 22% or > 32%, headroom > 3%, or bottom edge < 60% or > 75%.

PLACEMENT, SCALE & OPTICS
• One consistent perspective and focal length for all three. Keep faces on a similar focal plane for uniform sharpness.
• Natural relative head scales; no oversized or undersized heads.

LIGHTING & BACKGROUND — GOLDEN HOUR
• Time/look: warm, soft, directional golden hour light (first/last hour). Gentle backlight or 3/4 backlight from camera-left; subtle rim on hair/shoulders; no harsh flares on faces.
• Fill: ambient sky or soft bounce so all faces are evenly exposed.
• White balance: warm daylight; keep golden tones (no cool cast).
• Background: real outdoor field/park with tall grass or treeline; softly blurred; no bright hotspots crossing faces; coherent sun direction, shadows, and color across subjects.

WARDROBE & COLOR PALETTE
• Soft neutrals + warm earthy accents (cream, beige, warm white, stone gray; optional sage/rust/terracotta). No neon, no stark pure black. No new accessories or haircuts.

AESTHETIC RECIPE (without altering identity)
• Lens: 50–65 mm equivalent. Distance: ~1.2–1.6 m for mid-torso framing.
• Aperture: ~f/3.5–f/4.0 to keep all faces sharp with pleasant background blur.
• Composition shape: gentle triangle of heads; adults’ shoulders arc protectively around the child.
• Texture fidelity: preserve freckles/pores/micro-contrast; no smoothing/whitening/face-slimming.
• Finish: crisp hair edges (no halos), even exposure on all faces, no vignettes.

NEGATIVE CONSTRAINTS (forbid)
• Missing subjects; >10% occlusion of any face; age/sex changes; new accessories/haircuts.
• CGI/painting/anime/HDR/over-sharpening; plastic skin; symmetry forcing; makeup airbrushing.
• Identity blending; cross-person feature transfer; mismatched head scales; warped glasses; elongated/shortened necks; misaligned eyes; haloing; perspective or color-temperature mismatch.
• Extra people, text, logos, watermarks, frames, borders, or black bars.

FINAL SELF-CHECK (must all be TRUE; otherwise regenerate)
1) Mother is a literal 1:1 match to her references (geometry, textures, hairline/part, features).
2) Father is a literal 1:1 match to his references (geometry, textures, hairline/part, features).
3) Child is a literal 1:1 match to her reference (geometry, textures, hairline/part, features).
4) Left → right order is MOTHER — CHILD — FATHER; no identity leakage.
5) No borders/black bars; full-bleed 9:16.
6) Composition lock satisfied: adult eyes 24–30%; child 36–44%; headroom ≤ 3%; bottom edge 63–72%; no elbow/wrist chops.
7) Lighting, perspective, and white balance are coherent across all three subjects.

"""
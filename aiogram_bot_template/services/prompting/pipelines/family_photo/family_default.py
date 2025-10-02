PROMPT_FAMILY_DEFAULT = """
GOAL
Create ONE photorealistic, full-bleed 9:16 family portrait using ONLY attached image. Do NOT invent, blend, beautify, or “normalize” identities.

INPUT LAYOUT (fixed)
• First line of image = MOTHER: contains exactly two portraits of the same person (one front/straight-on, one clean side profile).
• Second line of image = FATHER: contains exactly two portraits of the same person (one front/straight-on, one clean side profile).
• Third line of image = CHILD: contains exactly one front/straight-on portrait.

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

POSE / INTERACTION
• Arrange a natural close group embrace — Mother, Child, and Father gently hugging, relaxed posture, no face occlusion, hands placed naturally (no awkward limb crops).

LIGHTING & BACKGROUND — GOLDEN HOUR
• Time/look: warm, soft, directional golden hour light (first/last hour). Gentle backlight or 3/4 backlight from camera-left; subtle rim on hair/shoulders; no harsh flares on faces.
• Fill: ambient sky or soft bounce so all faces are evenly exposed.
• White balance: warm daylight; keep golden tones (no cool cast).
• Background: real outdoor field/park with tall grass or treeline; softly blurred; no bright hotspots crossing faces; coherent sun direction, shadows, and color across subjects.

WARDROBE & COLOR PALETTE
• Soft neutrals + warm earthy accents (cream, beige, warm white, stone gray; optional sage/rust/terracotta). No neon, no stark pure black. No new accessories or haircuts.

FINAL SELF-CHECK (must all be TRUE; otherwise regenerate)
0) Image is full-bleed; not a collage.
1) Mother is a literal 1:1 match to her references (geometry, textures, hairline/part, features).
2) Father is a literal 1:1 match to his references (geometry, textures, hairline/part, features).
3) Child is a literal 1:1 match to her reference (geometry, textures, hairline/part, features).
4) Left → right order is MOTHER — CHILD — FATHER; no identity leakage.
5) No borders/black bars; full-bleed 9:16.
6) Composition lock satisfied: adult eyes 24–30%; child 36–44%; headroom ≤ 3%; bottom edge 63–72%; no elbow/wrist chops.
7) Lighting, perspective, and white balance are coherent across all three subjects.

"""
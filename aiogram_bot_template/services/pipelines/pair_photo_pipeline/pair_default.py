PROMPT_PAIR_DEFAULT = """
GOAL: Create ONE photorealistic, full-bleed 9:16 couple portrait using ONLY the attached stacked image. Do NOT invent, blend, or beautify identities.

INPUT LAYOUT (fixed)
• Top half of image = PERSON A: contains one front/straight-on view and one clean side profile view.
• Bottom half of image = PERSON B: contains one front/straight-on view and one clean side profile view.

IDENTITY PIPELINE
• For EACH person, build a separate ID embedding from their two reference views to recover true 3D facial geometry.
• Maximize internal face-embedding similarity to each reference. Identity fidelity > aesthetics.

STRICT ID LOCKS (no beautification)
• Preserve exact facial geometry, proportions, and natural asymmetry from the references for both individuals. Do NOT slim faces, alter noses, or smooth skin.
• Copy 1:1 all unique features: brow shape, eye canthus tilt, iris color, interpupillary distance, nose bridge/width/tip, philtrum, Cupid’s bow, lip volume, jaw angle, chin silhouette, ear shape, hairline/part, color, length, freckles/pores/moles, and skin tone for both Person A and Person B.
• Absolutely no borrowing/averaging of features across people. Keep two distinct identities.

NOT A COLLAGE
• Reconstruct full heads, hairlines, necks, and shoulders. No floating heads or pasted looks.

COMPOSITION & POSE
• Arrange a natural close couple pose. They can be standing close, perhaps one slightly behind the other, with a gentle, relaxed posture.
• Both individuals should be looking towards the camera with soft, friendly expressions.
• Framing: medium-close, chest-up.

LIGHTING & BACKGROUND — GOLDEN HOUR
• Time/look: warm, soft, directional golden hour light. Gentle backlight or 3/4 backlight; subtle rim on hair/shoulders; no harsh flares on faces.
• Fill: ambient sky or soft bounce so both faces are evenly exposed.
• Background: real outdoor field/park with tall grass or treeline; softly blurred; coherent sun direction.

WARDROBE
• Soft neutrals + warm earthy accents (cream, beige, warm white, sage, rust). No neon, no stark black, no logos or bold prints.

FINAL SELF-CHECK
1) Image is full-bleed; not a collage.
2) Person A is a literal 1:1 match to their references.
3) Person B is a literal 1:1 match to their references.
4) No identity leakage between the two people.
5) Lighting, perspective, and white balance are coherent across both subjects.
"""
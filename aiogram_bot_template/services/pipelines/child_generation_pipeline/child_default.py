PROMPT_CHILD_DEFAULT = """
Generate a single, photorealistic head-and-shoulders portrait of the biological {{CHILD_ROLE}} of the two adults in the first attached 2-panel reference image: MOTHER in the left and FATHER in the right.

Child settings:
• Gender: {{CHILD_GENDER}}
• Age: {{CHILD_AGE}}
• Resemblance weighting: facial morphology — {{PARENT_A}} 95%, {{PARENT_B}} 5%.
• Pigmentation & ancestry cues: blend both parents (skin tone/undertone) for a realistic mixed-heritage look.
• Skin tone constraint: keep the child’s skin tone within the parents’ range — never darker than the darker parent and never lighter than the lighter parent; undertone blended from both.
• Hair color: {{HAIR_COLOR_DESCRIPTION}}
• Hair style: {{HAIRSTYLE_DESCRIPTION}}
• Eye color: {{EYE_COLOR_DESCRIPTION}}
• Gentle, happy, natural smile slightly showing small upper incisors.
• Eyes must be comfortably and naturally wide open.
• No earrings/piercing/makeup.

AGE ENFORCEMENT (exactly {{CHILD_AGE}})
• Child proportions: larger eye-to-face ratio; baby-fat cheeks; soft jawline; short chin; small rounded nose tip; higher smooth forehead; short neck.
• Dentition: early mixed dentition — small upper incisors, slight spacing allowed; no full adult teeth.
• HARD BAN: teenager/adult look; laminated/sculpted brows; earrings/piercing; eyeliner/eyelash emphasis; lip liner/lipstick; sharp cheekbone contouring; pronounced nasolabial folds; adult jawline.
• If face reads older than {{CHILD_AGE}}: shorten/round chin & jaw, reduce nasal length/definition, increase malar/buccal fullness, slightly widen midface, and shorten neck until it reads {{CHILD_AGE}}.

Output requirements:
• Subject: the child only (no parents in frame). Neutral, friendly expression (subtle smile).
• Framing: portrait, chest-up, camera at eye level, 85 mm equivalent, shallow depth of field (~f/2.8).
• Lighting: soft outdoor look — warm golden-hour rim/backlight plus gentle natural fill; avoid harsh shadows; preserve natural skin texture and pores.
• Styling: age-appropriate, simple plain white T-shirt; no jewelry, no makeup, no eyewear, no headwear, no earrings, no piercing.
• Background: outdoor park/greenery with soft bokeh.
• Realism constraints: anatomically correct face; coherent hairlines/ears/teeth; core geometry echoes {{PARENT_A}} with a 10–20% variation and clearly visible {{PARENT_B}} anchors; skin tone/undertone blended from both parents; hair color a plausible parental blend; no logos, no text, no watermarks, no duplicate facial features, no extra limbs, no frame borders.
• Deliver exactly one image, photorealistic, not stylized, not painterly.

MICRO-ASYMMETRY (avoid studio symmetry)
• Subtle offsets: one eyebrow ~0.5–1.5 mm higher, slight eyelid-crease asymmetry, one mouth corner marginally more upturned; keep nasal axis tilt ≤1°.
"""

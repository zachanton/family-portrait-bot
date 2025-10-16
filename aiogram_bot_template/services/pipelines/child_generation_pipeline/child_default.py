PROMPT_CHILD_DEFAULT = """
Look at the reference photo: study the {{PARENT_A}}'s face (left person) CAREFULLY.
Now create {{CHILD_AGE}}-year-old {{CHILD_ROLE}} who looks EXACTLY like a younger version of this person.

Generate a {{CHILD_AGE}}-year-old {{CHILD_GENDER}} using the {{PARENT_A}}(left person) from the reference image as the PRIMARY genetic template. 

Imagine taking the {{PARENT_A}}'s face and age-regressing it to childhood:
- Keep exact feature placement and proportions
- Maintain distinctive brows, eyes, nose and mouth shape
- Preserve facial geometry
- Simply soften everything for a {{CHILD_AGE}}-year-old {{CHILD_GENDER}}

This is essentially the {{PARENT_A}} at age {{CHILD_AGE}}.

Genetics: 90% {{PARENT_A}}, 10% {{PARENT_B}} influence.

ADDITIONAL CHILD SETTINGS:
• Happy-friendly expression; gentle, happy, natural smile slightly showing upper teeth; eyes innocently wide-open.
• Skin/ancestry: {{SKIN_TONE_ETHNICITY_DESCRIPTION}}
• Hair color: {{HAIR_COLOR_DESCRIPTION}}; hair style: {{HAIRSTYLE_DESCRIPTION}}
• Eyes color: {{EYE_COLOR_DESCRIPTION}}
• Bias toward the widest non-surprised look.

POSE / RENDER:
• Head pose neutral; yaw/pitch/roll ≤2°. Eye-level camera; ≈85 mm; shallow DoF ≈f/2.8.
• Soft outdoor golden-hour rim/backlight + gentle fill. Plain white T-shirt. Background: greenery bokeh.
• Realism: anatomically coherent hairline/ears/teeth; natural skin texture; exactly ONE image; no text/logos/watermarks/duplicates.

AGE APPEARANCE LOCK ({{CHILD_AGE}} y/o):
• Pediatric proportions via SCALING ONLY on the {{PARENT_A}}'s cloned features. Mild buccal fullness.

MICRO-ASYMMETRY (natural):
• Inherit the {{PARENT_A}}'s natural asymmetries. Subtle left/right differences: one brow ≈1–2 mm higher, smile corner ≈1–2 mm higher, tiny nostril width offset ≈2–3%, slight hair part irregularity. Keep it organic.

FAILURE CHECK: If the result looks like it could be any random child from a stock photo, you've failed. The resemblance must be UNDENIABLE.

"""
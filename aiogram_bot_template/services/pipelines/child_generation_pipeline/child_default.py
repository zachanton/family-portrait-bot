# --- UPDATED: Added RESEMBLANCE_FEATURES_BLOCK placeholder ---
PROMPT_CHILD_DEFAULT = """
PRIORITY: 1) {{PARENT_A}}'s identity lock > 2) Age morphology > 3) Style.

Generate ONE photorealistic chest-up portrait of the 6-year-old biological son, genetically inherited from both adults in the reference image ({{PARENT_A}}'s front in the left, {{PARENT_B}}'s profile in the right).

The primary goal is an EXTREME LIKENESS to the {{PARENT_A}}, with all unique facial structures adapted to a {{CHILD_AGE}}-year-old {{CHILD_GENDER}} morphology.

RESEMBLANCE LOCK ({{PARENT_A}}):
{{RESEMBLANCE_FEATURES_BLOCK}}

SUBJECT SETTINGS:
• Gender: {{CHILD_GENDER}}. Age: {{CHILD_AGE}}. Neutral-friendly expression; subtle smile with small visible upper incisors; eyes naturally open (not surprised).
• Skin/ancestry: {{SKIN_TONE_ETHNICITY_DESCRIPTION}}
• Hair: {{HAIR_COLOR_DESCRIPTION}}; style: {{HAIRSTYLE_DESCRIPTION}}.
• Eyes: {{EYE_COLOR_DESCRIPTION}}.

AGE APPEARANCE LOCK ({{CHILD_AGE}} y/o):
• Pediatric proportions via SCALING ONLY on the {{PARENT_A}}'s cloned features. Mild buccal fullness.
• Early mixed dentition: no large broad permanent incisors.

HARD NEGATIVES:
• NO generic oval face. NO "button nose" or overly upturned nose. NO overly full lips unless they are a direct match to the parent.

POSE / RENDER:
• Head pose neutral; yaw/pitch/roll ≤2°. Eye-level camera; ≈85 mm; shallow DoF ≈f/2.8.
• Ensure eyes–brows–nose and jawline are fully visible (no hair over brows).
• Soft outdoor golden-hour rim/backlight + gentle fill. Plain white T-shirt. Background: greenery bokeh.
• Realism: anatomically coherent hairline/ears/teeth; natural skin texture; exactly ONE image; no text/logos/watermarks/duplicates.

MICRO-ASYMMETRY (natural):
• Inherit the {{PARENT_A}}'s natural asymmetries. Subtle left/right differences: eye aperture ≈2–4%, one brow ≈1–2 mm higher, smile corner ≈1–2 mm higher, tiny nostril width offset ≈2–3%, slight hair part irregularity. Keep it organic.

"""
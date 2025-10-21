PROMPT_PAIR_DEFAULT = """
OUTPUT: one photorealistic, full-bleed couple portrait — SINGLE, UNBROKEN FRAME (no split-screen, no collage, no grid).

INPUT LAYOUT (fixed, references only — DO NOT reproduce this layout in the final image):
• Top = WOMAN: front + clean side profile.
• Bottom = MAN: front + clean side profile.

PRIORITY: IDENTITY > framing > style.

IDENTITY — lock from the two views per person:
• Use only these two photos per person to reconstruct 3D face + hairline.
• Match: skull/jaw contour, nose shape & width, philtrum/lip volume, eye shape/spacing, eyebrow thickness/arch, hairline/part, ear shape/attachment.
• Keep natural asymmetry, freckles/moles/pores.
• Strictly preserve prescription glasses from the reference. Keep existing prescription glasses; **do not add new ones if absent.**
• Don’t change age/weight; don’t beautify; don’t smooth skin; don’t alter head-size ratio between people.

FRAMING — {{STYLE_NAME}} “{{SCENE_NAME}}” (single frame)
{{FRAMING_OPTIONS}}

STYLE — {{STYLE_DEFINITION}}, {{SCENE_NAME}}
{{STYLE_OPTIONS}}

GAZE — lock precise alignment: for each person both eyes converge to the same target, pupils equal size with single mirrored catchlights; forbid divergent/crossed gaze, misaligned irises, or inconsistent catchlight positions.

HARD NEGATIVES:
• Do not render a collage/diptych/grid/split screen. Ignore the INPUT LAYOUT for composition — it is for identity locking only.
• No face swap/averaging. No slimming, geometry changes, or skin smoothing that removes micro-texture.
• Render hands naturally; strictly forbid finger interlacing/interlocking between individuals.
• No heavy HDR, teal-orange overgrade, strong vignette, or visible brand logos/signage.
• Identity overrides style in every conflict.
• No full-tooth smiles; smiles must be closed-lip or at most slightly reveal the upper teeth (never fully visible).

GENERATION ORDER:
1) Lock identity (front + profile per person).
2) Apply FRAMING.
3) Apply STYLE.
4) Subtle cleanup only (edges/eyes/hair); avoid skin smoothing or ID drift.

"""
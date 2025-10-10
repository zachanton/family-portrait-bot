PROMPT_PAIR_DEFAULT = """
OUTPUT: one photorealistic, full-bleed couple portrait — SINGLE, UNBROKEN FRAME (no split-screen, no collage, no grid).

INPUT LAYOUT (fixed, references only — DO NOT reproduce this layout in the final image):
• Top = WOMAN: front + clean side profile.
• Bottom = MAN: front + clean side profile.

PRIORITY: IDENTITY > framing > style.

IDENTITY — lock from the two views per person:
• Use only these two photos per person to reconstruct 3D face + hairline.
• Match: skull/jaw contour, nose shape & width, philtrum/lip volume, eye shape/spacing, eyebrow thickness/arch, hairline/part, ear shape/attachment.
• Keep natural asymmetry, freckles/moles/pores. Keep glasses, earrings.
• Don’t change age/weight; don’t beautify; don’t smooth skin; don’t alter head-size ratio between people.

FRAMING — {{STYLE_NAME}} “{{SCENE_NAME}}” (single frame)
{{FRAMING_OPTIONS}}

STYLE — {{STYLE_DEFINITION}}, {{SCENE_NAME}}
{{STYLE_OPTIONS}}
Glasses(if exist): raise key +12° or rotate head +8° toward key; add small warm bounce below lens line; optional on-axis soft fill −1 EV; allow pantoscopic tilt ~10°; micro-dodge under rim +0.15 EV (keep skin texture).


HARD NEGATIVES:
• Do not render a collage/diptych/grid/split screen. Ignore the INPUT LAYOUT for composition — it is for identity locking only.
• No face swap/averaging. No slimming, geometry changes, or skin smoothing that removes micro-texture.
• Render hands naturally; strictly forbid finger interlacing/interlocking between individuals.
• No heavy HDR, teal-orange overgrade, strong vignette, or visible brand logos/signage.
• No under-rim or nose-pad shadows on faces; no frame-cast shadows across eyes.
• Identity overrides style in every conflict.

GENERATION ORDER:
1) Lock identity (front + profile per person).
2) Apply FRAMING.
3) Apply STYLE.
4) Subtle cleanup only (edges/eyes/hair); avoid skin smoothing or ID drift.

"""
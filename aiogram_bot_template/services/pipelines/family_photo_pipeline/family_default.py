# aiogram_bot_template/services/pipelines/family_photo_pipeline/family_default.py

PROMPT_FAMILY_DEFAULT = """
OUTPUT: one photorealistic, full-bleed family portrait — SINGLE, UNBROKEN FRAME (no split-screen, no collage, no grid).

INPUT LAYOUT (fixed, references only — DO NOT reproduce this layout in the final image):
• Top Row = MOTHER: front + clean side profile.
• Middle Row = FATHER: front + clean side profile.
• Bottom Row = CHILD: front view only.

PRIORITY: IDENTITY > framing > style.

IDENTITY — lock from the reference views for each person:
• Use only the provided photos for each person to reconstruct their 3D face + hairline.
• Match: skull/jaw contour, nose shape & width, philtrum/lip volume, eye shape/spacing, eyebrow thickness/arch, hairline/part, ear shape/attachment for ALL THREE people.
• Keep natural asymmetry, freckles/moles/pores. Keep existing glasses or earrings.
• Don’t change age/weight; don’t beautify; don’t smooth skin; don’t alter head-size ratios.
• Ensure NO feature blending between the three distinct individuals.

FRAMING — {{STYLE_NAME}} “{{SCENE_NAME}}” (single frame)
{{FRAMING_OPTIONS}}

STYLE — {{STYLE_DEFINITION}}, {{SCENE_NAME}}
{{STYLE_OPTIONS}}

HARD NEGATIVES:
• Do not render a collage/diptych/grid. The INPUT LAYOUT is for identity reference ONLY.
• No face swap/averaging. No slimming, geometry changes, or skin smoothing that removes micro-texture.
• No heavy HDR, teal-orange overgrade, strong vignette, or visible brand logos/signage.
• Identity overrides style in every conflict.

GENERATION ORDER:
1) Lock identity for Mother, Father, and Child independently.
2) Apply FRAMING and position all three subjects in a single, coherent scene.
3) Apply STYLE.
4) Subtle cleanup only (edges/eyes/hair); avoid skin smoothing or ID drift.
"""
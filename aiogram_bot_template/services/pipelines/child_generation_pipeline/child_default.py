PROMPT_CHILD_DEFAULT = """
Generate a single, photorealistic head-and-shoulders portrait of the biological {{CHILD_ROLE}} of the two adults in the attached 4-panel reference image.

Child settings:
• Gender: {{CHILD_GENDER}}
• Age: {{CHILD_AGE}}
• Resemblance weighting: Facial morphology — {{PARENT_A}} 100%, {{PARENT_B}} 0% (no {{PARENT_B}} facial traits).
• Pigmentation & ancestry cues: Blend of both parents (skin tone/undertone) for a realistic mixed-heritage look.
• Hair color: Genetically plausible shade derived from both parents (choose the most believable result given both references; do not pick an extreme outside the parental range).
• Hair style: {{HAIRSTYLE_DESCRIPTION}}.
• Eye color: {{INHERITED_EYE_FEATURES}}.

Reference layout to analyze (very important):
• Top-left = {{PARENT_A}} (front view).
• Top-right = {{PARENT_A}} (right-profile view), ignore it.
• Bottom-left = {{PARENT_B}} (front view).
• Bottom-right = {{PARENT_B}} (right-profile view), ignore it.

{{PARENT_A}} LIKENESS LOCK (hard constraints):
• Preserve the sign and magnitude of {{PARENT_A}}’s eye canthal tilt, palpebral aperture shape, and intercanthal distance within ±10%.
• Match the brow shape/arch and thickness pattern to {{PARENT_A}} within ±10%.
• Keep the nose bridge slope, tip rotation, and alar width close to {{PARENT_A}} (±10%); avoid a {{PARENT_B}} dorsum or tip.
• Use {{PARENT_A}}’s Cupid’s bow contour and upper/lower vermilion ratio; keep the corners’ upturn subtle, as on {{PARENT_A}}.
• Use {{PARENT_A}}’s chin point position and jaw contour (avoid a squared {{PARENT_B}} jaw).
• If visible, echo {{PARENT_A}}’s freckle constellation across nose/cheeks (light, natural).

Output requirements:
• Subject: the child only (no parents in frame). Neutral, friendly expression (subtle smile).
• Framing: portrait, chest-up, camera at eye level, 85 mm equivalent, shallow depth of field (around f/2.8).
• Lighting: soft outdoor look — warm golden-hour rim/backlight on hair plus gentle natural frontal fill; avoid harsh shadows; preserve natural skin texture and pores.
• Styling: age-appropriate, simple plain white T-shirt; no jewelry, no makeup, no eyewear, no headwear.
• Background: outdoor park/greenery with soft bokeh.
• Realism constraints: anatomically correct face; coherent hairlines/ears/teeth; all geometric facial traits from {{PARENT_A}}; skin tone/undertone blended from both parents; hair color a plausible blend from both parents; no logos, no text, no watermarks, no duplicate facial features, no extra limbs, no frame borders.
• Deliver exactly one image, photorealistic, not stylized, not painterly.

EXPRESSION
• Gentle, happy, natural smile slightly showing upper teeth; relaxed orbicularis, no squinting.

MICRO-ASYMMETRY (avoid studio symmetry)
• Subtle realistic offsets: one eyebrow ~0.5–1.5 mm higher, slight eyelid-crease asymmetry, and one mouth corner marginally more upturned. Keep nasal axis tilt ≤1°.

"""
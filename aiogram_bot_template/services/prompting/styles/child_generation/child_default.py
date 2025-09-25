PROMPT_CHILD_DEFAULT = """
Generate **one vertical 9:16** photorealistic portrait of a **{{child_age}}-year-old {{child_gender}}**. The child must instantly read as real and **clearly resemble the person in Image A** while staying age-accurate.

**INPUT REFERENCES (do not display in output)**

* **Image A — Resemblance Parent** → primary identity anchor.

**GLOBAL RESEMBLANCE & AGE**

* Target resemblance to **Image A = 92–95%** while keeping child craniofacial ratios: larger cranial vault vs mandible, fuller midface, softer jawline, **slightly shorter philtrum**, smaller nasal spine, and smaller teeth. **Never transfer adult age markers** (wrinkles, stubble, makeup shaping).

**FEATURE LOCKS (copy from Image A, then scale to child)**

* **Eyebrows:** keep the parent’s arch vs straightness, average thickness, start/stop points, and spacing; hue in the same family, **~10% lighter than hair**. **Brows must be fully visible**; avoid heavy bangs/fringe unless required by {{HAIRSTYLE_DESCRIPTION}}.
* **Eyes / Eyelids:** match **iris hue family and pattern** from Image A (include gray/green/brown undertones, limbal ring strength, heterochromia if present). Keep parent’s **palpebral fissure tilt**, inter-canthal distance proportion, and eyelid-crease height, then open to a neutral child aperture. Preserve left/right micro-differences.
* **Nose:** preserve dorsal profile type (straight vs slight concavity), **bridge height at the radix**, and tip projection trend of the parent; adapt alar width to child but keep parent’s relative narrowness/width cues.
* **Mouth/Lips/Philtrum:** keep the parent’s **Cupid’s bow shape** and **upper:lower vermilion ratio** (±10%); smile with **slightly visible upper teeth**; corners not perfectly symmetrical.
* **Chin/Jaw/Cheekbones:** soften to child fat pads, but keep the parent’s **chin point alignment** and general face shape (oval/heart/round) and cheekbone height trend.
* **Skin & Marks:** match undertone and **replicate parent’s freckles/moles distribution** at subtle, child density (do not erase them).
* **Hair:** color family from Image A, **~20% lighter**, subtle sun-kissed ends, a few flyaways/baby hairs.
  Hair style: **{{HAIRSTYLE_DESCRIPTION}}** // style only; keep hairline shape inherited from parent.
* **{{INHERITED_EYE_FEATURES}}** // apply alongside the eye instructions above.

**EXPRESSION**

* Gentle, happy, natural smile **showing upper teeth** slightly; relaxed orbicularis, no squinting.

**MICRO-ASYMMETRY (avoid studio symmetry)**

* Subtle realistic offsets: one eyebrow **~0.5–1.5 mm higher**, slight eyelid-crease asymmetry, and one mouth corner marginally more upturned. Keep nasal axis tilt ≤1°.

**WARDROBE**

* **Plain white T-shirt**, short sleeves, **no logos/patterns/graphics**.

**COMPOSITION & LIGHT**

* **Bust / upper-torso portrait** with full shoulders and collarbones; bottom crop at **mid-chest**.
* **Minimal headroom (1–3%)**, **eye line ≈30% from top**, **do not crop the forehead**.
* Outdoor park/greenery with soft bokeh. Warm golden-hour rim/backlight on hair + gentle natural frontal fill. Recompute shadows/reflections/catchlights consistently.

**REALISM SAFEGUARDS**

* Skin texture must look photographic (fine pores, subtle micro-speculars), **no beauty-filter smoothing**, no oversized eyes, no CGI sheen. Teeth proportionate to age.

**TWO-PASS LIKENESS CHECK (re-render once if needed)**

1. If likeness < ~90% or the face looks stylized/doll-like or eyes are even slightly narrow:
   a) Increase Image-A bias **+10–15% specifically for eyebrows, eye shape/tilt, iris hue, nose bridge height, Cupid’s bow, and chin point** (keep child alar width).
   b) Correct iris hue toward the parent’s exact spectrum (avoid default bright-blue drift); ensure eyelid aperture is neutral child-wide.
   c) Reinstate freckles/moles and micro-asymmetry; keep **upper teeth slightly visible**.
2. Re-render once with these corrections.

**DO NOT**

* No parents in frame; no extra people; no cloning of an adult face; no heavy makeup; no HDR halos; no text/borders/watermarks; no extreme bilateral symmetry; no matte/black borders.

"""
PROMPT_CHILD_GENERATION = """
Create ONE photorealistic portrait of a {{child_age}}-year-old {{child_gender}} from two adult references.
At first glance the child must clearly resemble the {{child_resemblance}} (PRIMARY). The result must be a real kid, not an aged-down adult.

INPUTS
• Image A — both parents (global palette/skin range).
• Image B — PRIMARY face crop (micro-traits anchor). Treat both as TRAITS ONLY.

SUBJECT
• Exactly 1 person — the child. No background people.

RESEMBLANCE (very strong; prioritize Image B)
• Global identity should read ~99% PRIMARY.
• REGION LOCKS from Image B (PRIMARY) (weight 1.0): eye shape & canthus, brow shape (lightened for a child), smile & lip geometry, philtrum proportion, nose tip/width, chin contour, cheekbone layout, freckle map, hairline.
• From SECONDARY ONLY: iris color & detailed pattern (match exactly; no averaging/hue drift).
• Synthesize a new juvenile face; never paste/age-down a parent.

AGE LOOK
• Child anatomy: rounder cheeks, softer jaw, shorter philtrum; remove adult artifacts (wrinkles, makeup, stubble). Average build.

EYES (open, childlike — no squint)
• Do **not** inherit parental squint/half-closed lids.
• Keep PRIMARY eye **shape & canthal tilt**, but set a **neutral-open palpebral fissure**:
  – height **+35–45%** vs. parent averages; width **+10–15%**.
  – Upper lid covers **~1–2 mm** of the iris; lower lid tangent to iris or **0–0.5 mm** scleral show.
  – No upper-sclera show (avoid startled look).
• During the smile, **minimize orbicularis oculi compression**: cheeks may rise, but lids stay relaxed (avoid Duchenne squint and crow’s-feet).
• Natural round catchlights; irises locked to the SECONDARY parent exactly (no averaging).
• If eyes still read narrow → increase fissure height **+10%** and reduce cheek raise **−15%**, then re-render.

TEETH & SMILE
• Open, happy child smile with **only the upper teeth visible** (6–8). Do not show the lower row.
• Teeth intact; tiny natural irregularities; not veneer-white. If unreliable → closed-lip smile.

HAIR & BROWS (color rules)
• Hair family from PRIMARY, ~20% lighter with soft sun-kissed ends; a few flyaways.
• Brows same hue family, ~20% lighter than hair; sparser/softer.
• Styling: girls — classic long child hair; boys — short neat child cut.

SKIN & FRECKLES
• Real skin texture (pores, mild sheen). Freckles follow PRIMARY’s pattern with natural variation; keep clean skin between spots.

COMPOSITION (match the reference look)
• Medium portrait with shoulders and upper chest visible; child centered, eye level.
• Subject fills ~45–55% of frame height; generous headroom (~12–15%); do not crop the forehead.
• Camera distance ~1.5–2.0 m; portrait look 85–105 mm equiv., shallow DoF (f/1.8–f/2.8).
• Outdoor park/greenery background with creamy bokeh; warm backlight/rim plus gentle frontal fill; no people or strong structures.

NATURAL MICRO-ASYMMETRY (avoid perfect symmetry)
• Subtle left/right differences: eye aperture ≈2–4%, one brow ≈1–2 mm higher, smile corner ≈1–2 mm higher, tiny nostril width offset ≈2–3%, slight hair part irregularity. Keep it organic.

DO-NOTS
• No extra people, CGI/cartoon look, heavy makeup, braces, missing/broken teeth, borders/watermarks/text.

OUTPUT
• PNG, 1536×1920 (4:5).
"""

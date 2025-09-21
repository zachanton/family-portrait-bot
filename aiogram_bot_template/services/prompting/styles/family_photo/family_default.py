PROMPT_FAMILY_DEFAULT = """
OUTPUT FIRST
Create ONE photorealistic outdoor family portrait made by an external camera. Exactly three people: MOM, CHILD, DAD. 4K PNG, portrait orientation (≈3:2), full-bleed.

IDENTITY REFERENCES (UNIVERSAL)
Use the uploaded image(s) ONLY as identity references. Detect three distinct faces and assign anchors by reading order (top→bottom if stacked, else left→right):
• Anchor A → MOM (adult woman)
• Anchor B → CHILD (youngest person)
• Anchor C → DAD (adult man)
Never average, swap, or blend anchors; ignore borders/crops/backgrounds.

DIRECT TRANSFER — RELIGHT ONLY
Transfer each face AND hairstyle from its anchor into the new scene with relighting only. No resculpting or beautification.

HARD IDENTITY LOCKS — MUST MATCH 1:1
• Geometry: head/face outline; forehead height & hairline contour; cheekbones; jaw/chin width/angle; inter-ocular distance; eye size/shape & eyelid crease; canthus angles; eyebrow thickness/arch/spacing; nose bridge–tip–length–alar base width; philtrum; lip outline/fullness & Cupid’s bow; mouth-corner tilt; dental midline; ear shape/attachment. Preserve asymmetries.
• Texture: pores, freckles, moles, wrinkles, under-eye texture, beard stubble; natural tooth shade. No smoothing, slimming, whitening, or eye enlargement; no makeup addition.
• Hair: exact parting direction, hairline shape, apparent length, curl/straightness, volume/density; include baby hairs/flyaways; preserve facial hair pattern. Only tiny wind/lighting changes; no new bangs/parting; no length/volume jumps; no hue shift out of the original color family.
• Color & tone: keep iris color, base hair color, and skin undertone (face–neck–hands must match).
• Accessories (if present): keep glasses, earrings, piercings, visible birthmarks.

SCENE, OPTICS & LIGHT
Golden-hour meadow; sun low behind subjects; warm rim light + soft bounced fill camera-left; consistent occlusion/shadows on hair and shoulders.
Camera eye-level; 85–105 mm full-frame equivalent at f/2.0–2.8; shallow DOF with smooth bokeh.

STRICT FRAMING — KNEE-UP ENFORCEMENT
• Composition: triangular grouping, CHILD centered and slightly forward; left→right order: MOM — CHILD — DAD.
• Frame **all three from head to just below the knees** (both adult knees and the child’s knees fully visible). Hands, elbows, and forearms must be entirely inside the frame.
• Provide 5–10% headroom above the tallest head and 5–10% margin below the knees; do **not** crop above the patella.
• Achieve knee-up by **camera distance/repositioning**, not by post-crop zoom. If the result is shoulders- or waist-up, **step back and recompose** until knees are included.

WARDROBE (CAN CHANGE)
– MOM: ivory/light linen blouse or shirt, sleeves lightly rolled to mid-forearm.
– CHILD: simple cotton dress in cream/blush with short sleeves.
– DAD: light beige linen button-down, one button open, sleeves rolled; untucked.

EXPOSURE & COLOR GUARDRAILS
Protect facial micro-detail; no clipped highlights on foreheads/noses/cheeks. Neutral skin white balance before grading; add light film grain rather than smoothing.

QUALITY CONTROL — FINAL CLOSE-CROP & FRAMING CHECK
1) Close-crop each face and verify: geometry, micro-texture, hairline/parting, iris color, and base hair color match anchors A/B/C exactly; if not, refit by **relighting only**.
2) Verify framing: both adult knees and the child’s knees are fully visible with 5–10% margin; if not, re-frame and re-render.

AVOID (HARD)
Different people; blended anchors; altered hairline/length; changed eye/lip/nose shapes; teeth/eye whitening; heavy smoothing; extra/missing people; head-and-shoulders, chest-up or waist-up crops; cut elbows/hands; text/panels/borders; CGI/illustration look.
"""
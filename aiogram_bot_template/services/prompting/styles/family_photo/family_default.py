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
• Head Position & Orientation Lock: The entire head unit (face, hair, ears) for each person must be transferred from the reference composite to the new scene, maintaining its exact 3D orientation (pitch, yaw, roll) and its position relative to the other two heads. Do not move, rotate, or tilt the heads. Only relighting is permitted.
• Gaze Lock: All three subjects (Mom, Dad, and Child) must be looking directly into the camera lens. Their gaze must not be directed at each other or away from the camera. Preserve their original expressions.
• Composition Lock: The final composition must strictly follow this left-to-right order: Anchor A (MOM) on the left, Anchor B (CHILD) in the center, and Anchor C (DAD) on the right. The child should be placed centrally, slightly in front of or between the parents. This spatial arrangement is mandatory and non-negotiable.
• Color & tone: keep iris color, base hair color, and skin undertone (face–neck–hands must match).
• Accessories (if present): keep glasses, earrings, piercings, visible birthmarks.
SCENE, OPTICS & LIGHT
Golden-hour meadow; sun low behind subjects; warm rim light + soft bounced fill camera-left; consistent occlusion/shadows on hair and shoulders.
Camera eye-level; 85–105 mm full-frame equivalent at f/2.0–2.8; shallow DOF with smooth bokeh.
POSE & COMPOSITION
Attach bodies to the fixed head positions from the reference image and execute the following pose, respecting the mandatory Mom-Child-Dad (left-to-right) composition:
{{POSE_AND_COMPOSITION_DATA}}
WARDROBE
{{PHOTOS_PLAN_DATA}}
EXPOSURE & COLOR GUARDRAILS
Protect facial micro-detail; no clipped highlights on foreheads/noses/cheeks. Neutral skin white balance before grading; add light film grain rather than smoothing.
QUALITY CONTROL — FINAL CLOSE-CROP CHECK
Close-crop each face and verify: geometry, micro-texture, hairline/parting, head tilt/angle, iris color, and base hair color match anchors A/B/C exactly; if not, refit by relighting only.
AVOID (HARD)
Different people; blended anchors; altered hairline/length; changed eye/lip/nose shapes; moving or re-orienting heads; subjects looking away from the camera or at each other; any compositional order other than Mom-Child-Dad left-to-right; teeth/eye whitening; heavy smoothing; extra/missing people; head-and-shoulders, chest-up or waist-up crops; cut elbows/hands; text/panels/borders; CGI/illustration look.
"""
PROMPT_FAMILY_DEFAULT = """
Create ONE photorealistic outdoor family portrait taken by an external camera. Exactly three people: MOM (adult woman), CHILD (youngest), DAD (adult man). 4K PNG, portrait orientation (~3:2), full-bleed.

OUTPUT & FRAMING
Edge-to-edge full-bleed at ~3:2 portrait. Do NOT add borders, mattes, or black bars (no letterboxing or pillarboxing). If any generation marks/logos are visible, crop them out while keeping the 3:2 ratio.

IDENTITY REFERENCES — HOW TO USE THEM
Use the uploaded image(s) ONLY for identity (face + hair). Detect three distinct faces and assign anchors by reading order (top→bottom if stacked; otherwise left→right):
• Anchor A → MOM (adult woman)
• Anchor B → CHILD (youngest person)
• Anchor C → DAD (adult man)
Do not average, swap, or blend anchors. Ignore reference backgrounds, borders, and crops.

PRIORITY
Identity fidelity > pose > style. Treat this as a context-aware edit: copy each head unit (face, hair, ears) from its anchor, relight for the new scene, and attach to the new bodies. No resculpting or beautification.

HARD IDENTITY LOCKS (must match 1:1)
• Geometry: head/face outline; hairline shape & forehead height; cheekbones; jaw/chin width & angle; inter-ocular distance; eye size/shape & eyelid crease; inner/outer canthus angles; eyebrow thickness/arch/spacing; nose bridge–tip–length–alar base width; philtrum length; lip outline/fullness & Cupid’s bow; mouth-corner tilt; visible tooth alignment; ear shape/attachment. Keep natural asymmetries. Do not slim, enlarge, equalize, or “fix”.
• Texture: pores, freckles, moles, fine wrinkles, under-eye texture, beard stubble. Keep natural tooth shade. No skin smoothing, whitening, eye enlargement, or makeup addition/removal.
• Hair (incl. facial hair): exact parting direction, hairline contour, apparent length, curl/straightness, volume/density, baby hairs and flyaways. Do not straighten/smooth texture; no new bangs/parting; no length/volume jumps; no color shift outside the original family.
• Age & sex: preserve perceived age and sex of each anchor; the child must remain a child; do not juvenilize adults or mature the child.
• Color & tone: preserve iris color, base hair color, and skin undertone; face–neck–hands must match.
• Accessories: keep glasses, earrings, piercings, and visible birthmarks exactly if present.

CHILD-SPECIFIC FIDELITY (Anchor B)
Preserve the exact freckle constellation (density and relative placement across nose and cheeks); preserve the eyebrow polygon (head–arch–tail thickness, flatness/arch, angles); keep the nasal bridge width and tip shape. Do not thicken, thin, or arch the eyebrows; do not narrow or round the nose tip. Maintain natural baby hairs and stray flyaways at the hairline; do not smooth or straighten hair texture.

DAD-SPECIFIC FIDELITY (Anchor C)
Preserve stubble density and distribution and the natural eyebrow asymmetry; do not soften, clean-shave, or symmetrize.

HEAD ORIENTATION, GAZE, EXPRESSION & TEETH
All three look directly into the camera. Match each person’s natural expression from their identity reference; do NOT change mouth openness. If a reference shows a closed-lip expression, do not generate visible teeth. If teeth are naturally visible in the reference, keep their natural alignment/size and dental midline; no whitening or reshaping. Minor head orientation adjustments are allowed only if they do not alter facial geometry or hairline.

COMPOSITION — STRICT ORDER
Mandatory left-to-right order: MOM on the left (Anchor A), CHILD centered and slightly in front/between the parents (Anchor B), DAD on the right (Anchor C). Maintain realistic scale (child smaller). No extra or missing people.

SCENE, LIGHTING & OPTICS
Golden-hour meadow; sun low behind subjects; warm rim light with soft bounced fill from camera-left; physically consistent occlusion/shadows on hair and shoulders.
Camera at eye level; 85–105 mm full-frame equivalent; f/2.0–2.8; shallow depth of field with smooth bokeh. Neutral white balance before any creative grading.

POSE & COMPOSITION (MUST OBEY ALL LOCKS)
{{POSE_AND_COMPOSITION_DATA}}

WARDROBE
{{PHOTOS_PLAN_DATA}}

EXPOSURE & RENDERING GUARDRAILS
Expose for skin; cap speculars to avoid clipping on foreheads, noses, and cheeks. Keep facial micro-detail visible even in highlights. Use subtle film grain instead of smoothing. No “beauty filter”, no teeth/eye whitening, no plastic skin, no CGI look.

QUALITY CONTROL — SELF-CHECK
Reject any image with borders/black bars or visible generation marks/logos inside the frame (crop them out while keeping 3:2). With tight face crops, verify for each anchor: geometry, micro-texture, hairline/parting and flyaways, iris color, freckle patterns (for the child), stubble density (for the dad), and base hair color match exactly. If any mismatch appears, re-fit by relighting only (no reshaping) and output the corrected single image.

AVOID (HARD)
Different identities; blended faces; changed eye/lip/nose shapes; altered hairline/length/parting; smoothing/retouching; subjects looking away from the camera or at each other; wrong left-center-right order; extra/missing people; borders/black bars; text or panels; non-photorealistic rendering.
"""
PROMPT_FAMILY_DEFAULT = """
Generate ONE photorealistic outdoor family portrait as an external-camera photo. Exactly three people in frame: MOM, CHILD, DAD. 4K PNG, full-bleed.

IDENTITY REFERENCES (UNIVERSAL MAPPING)
Use the uploaded image(s) ONLY as identity references. Detect distinct faces and assign anchors in reading order (top-to-bottom, left-to-right):
• Anchor A → MOM (adult woman)
• Anchor B → CHILD (youngest person)
• Anchor C → DAD (adult man)
If ages are ambiguous, keep the A→MOM, B→CHILD, C→DAD mapping by order. Never average, swap, or blend anchors.

HARD IDENTITY LOCKS — MUST MATCH 1:1
• Geometry lock: replicate head/face outline, cheekbones, jaw/chin, inter-ocular distance, eyelid crease and eye shape/size, nose (bridge/tip/width/length), philtrum, lip outline/fullness, eyebrow thickness/arch, and ear shape/attachment. Preserve natural asymmetries.
• Texture lock: keep real skin texture (pores, freckles, moles, wrinkles, stubble), natural tooth shade; NO beautification, smoothing, slimming, or eye enlargement.
• Hair lock: copy hairline shape, apparent length, parting direction, curl/straightness, volume; keep facial hair pattern if present. Allow only subtle changes from lighting/wind; NO new bangs/parting/length/volume jumps; color shift ≤ half a tone.
• Color & tone lock: match iris color and base hair color; match face–body skin undertone.
• Accessory lock (if present): keep glasses, piercings, visible birthmarks.
• Gaze & expression: all subjects look into the lens; aligned pupils; natural relaxed expression; plausible catchlights; no cross-eye.

WHAT MAY CHANGE (BODIES, WARDROBE, SCENE)
Build natural neck/shoulders/arms/torso that connect to the locked heads; do not resculpt faces to fit poses.
Wardrobe:
– MOM: ivory/light linen blouse or shirt with sleeves lightly rolled to mid-forearm.
– CHILD: simple cotton dress in cream/blush with short sleeves.
– DAD: light beige linen button-down, one button open, sleeves rolled; untucked.

SCENE, OPTICS, AND LIGHT
Golden-hour meadow with the sun low behind subjects; warm rim light and soft bounced fill from camera-left; consistent self-shadowing on hair and shoulders.
Camera at eye level; ~85 mm full-frame equivalent, f/2.0–2.8; subject distance ~2–3 m; shallow depth of field, smooth bokeh.
Framing: knee-up. Layout left→right: MOM — CHILD (center, slightly forward) — DAD.

QUALITY & VALIDATION
Photorealistic, no CGI/illustration look. One image only. Before finishing, run an identity-consistency check against anchors A/B/C; if any face or hairstyle deviates, refit geometry/texture/hair until it matches the anchors exactly.

AVOID (HARD)
Different people; blended anchors; altered hairline or hair length; changed face width/eye size/lip shape; heavy smoothing; makeup not present in the references; extra or missing people; text, panels, borders.
"""
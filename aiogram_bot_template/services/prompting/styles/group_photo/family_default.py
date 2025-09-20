PROMPT_FAMILY_DEFAULT = """
OUTPUT FIRST
Create ONE photorealistic family portrait captured by an external camera (not a selfie). EXACTLY three people: left adult, center child, right adult. Render at true 4K: long edge ≥ 4096 px. PNG, full-bleed.

INPUTS & ROLES
• Treat all input photos as identity references only; never reuse their backgrounds, borders, crops, or exposure.
• If a wide shot exists, use it ONLY for people placement (layout reference).
• Use any tight face crops as identity authority (faces and hairline edges).
• If references disagree, identity → hairline/microtexture → hairstyle silhouette, in that order.

INTENT
Synthesize one cohesive golden-hour meadow portrait. Rebuild the entire frame (background, bodies, wardrobe, light) while preserving the real identities, ages, and original hairstyles with documentary realism.

HARD IDENTITY LOCKS
1) Geometry: preserve each person’s craniofacial outline; cheekbones; jaw and chin width; inter-ocular distance; lid crease and eye shape; eyebrow shape/density; nose bridge/tip/width/length; philtrum; lip outline/fullness; ear shape/attachment; natural asymmetry.
2) Texture & color: retain authentic skin texture (pores, freckles, moles, under-eye detail), natural tooth shade and alignment, beard stubble coverage, and iris color/ring. No beautification, no AI smoothing.
3) Gaze & expression: all three look into the lens; aligned pupils with plausible catchlights (~10–11 o’clock); calm, natural expressions. No cross-eye or over-smile.

STRICT HAIR LOCK
• Match length and silhouette; keep the same part side/position; preserve hairline geometry (temples/widow’s peak), cowlicks, typical flow, and volume distribution.
• Preserve straight/wavy/curly pattern and highlight pattern; allow only lighting-driven warmth, not recoloring.
• No new bangs/fringe/braids/layers/volume jumps. Mirror ear-tuck vs. loose hair as seen in refs.
• Facial hair: preserve beard/mustache coverage, edge lines, density, and length; no shaving, no thickening.

WARDROBE (TIMELESS & COORDINATED — HARD)
Natural fabrics only (linen/cotton). Palette: cream, ivory, beige, sand, muted pastels. Matte textures, soft real wrinkles. No logos or busy patterns. No bare chest.
• Left adult: ivory linen blouse or light linen shirt, relaxed collar; sleeves lightly rolled to mid-forearm; small simple earrings allowed.
• Center child: plain cotton dress in cream/blush with short sleeves and gentle gathers — OR — light cotton tee/henley with a thin linen overshirt; no graphics.
• Right adult: light beige linen button-down, collar open one button; sleeves rolled to mid-forearm; shirt untucked; no undershirt visible.

COMPOSITION & POSE (MEDIUM SHOT — HARD)
Knee-up, order left → center (slightly forward) → right.
• Count and scale: exactly 3 people. Child clearly smaller than adults.
  – Child head height = 0.80–0.85× each adult’s.
  – Child shoulder width = 0.70–0.80× each adult’s.
  – Eye line: child’s eyes 2–4% lower in frame than adults’.
• Depth: child stands ~10–15 cm closer to camera for gentle depth while keeping the above ratios.
• Connected posing: left adult’s near hand gently on child’s shoulder/upper arm; right adult’s near hand relaxed at side or lightly behind child. Hands/fingers natural and anatomically correct.
• Framing: comfortable 3–5% headroom; avoid cropping at joints; no strong background tangents.

SCENE, OPTICS & LIGHT (SINGLE-CAMERA COHERENCE)
• Setting: open meadow at golden hour; sun low behind subjects; creamy, soft bokeh background; continuous ground plane and single horizon.
• Lighting: one coherent setup — warm back rim from the sun; soft bounced fill from camera-left at −1.0 to −1.5 EV relative to key; subtle negative fill from camera-right. Recompute all shadows/occlusions on faces, hair, and clothing; adjust speculars on skin and eyes accordingly.
• Camera: eye-level; ≈85 mm full-frame look at f/2.0–2.8; subject distance ~2–3 m; shallow DoF; ONE exposure and ONE white balance; smooth highlight roll-off; fine, film-like grain.

COHESION & ANTI-COLLAGE (HARD)
• Single frame only: no side-by-side panels, split backgrounds, borders, text, or watermarks.
• Remove any halos around hair; rebuild flyaways naturally.
• Unify grain/sharpness/contrast; no mismatched color temperatures; no pasted edges.
• Depth/perspective consistent; no duplicates or object tangents intersecting head contours.

WHAT MAY CHANGE
• Bodies only: synthesize natural necks/shoulders/arms/torso/legs connecting to locked heads; micro-pose adjustments allowed for a relaxed, connected family feel. Do not reshape faces or hair.

QUALITY & RESOLUTION
• Resolve fine identity cues (skin pores, freckles, beard stubble, baby hairs) at native 4K without over-sharpening halos or plastic smoothing.
• Avoid CGI look, HDR crunch, waxy skin, or denoise artifacts. Keep micro-contrast and authentic textures.

AVOID (HARD)
Different people; any change to face geometry or hair length/part/hairline/texture; plastic/CGI look; collage edges; mismatched exposure/white balance; extra people or missing people; text overlays.
"""
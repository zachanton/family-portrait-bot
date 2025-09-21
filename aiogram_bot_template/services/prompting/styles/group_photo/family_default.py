PROMPT_FAMILY_DEFAULT = """
OUTPUT FIRST
Create ONE photorealistic family portrait made by an external camera. EXACTLY three people in frame: MOM, CHILD, DAD. Render at true 4K . PNG, full-bleed.

INPUT IMAGE & ROLES (SINGLE COMPOSITE → THREE IDENTITY ANCHORS)
A single input image contains three faces side-by-side. Treat them as three separate identity references:
• MOM ← the uppermost person in the input (identity anchor A)
• CHILD ← the middle person in the input (identity anchor B)
• DAD← the lowermost person in the input (identity anchor C)
Use the input ONLY to learn identities and original hairstyles. IGNORE any black bars, crops, borders, backgrounds, or exposure from the input. Do NOT average or blend features across anchors.

**Edit intent**
Rebuild **bodies, wardrobe and scene** for a warm golden-hour couple portrait. **Do not alter facial identity.**

**Identity locks (must keep)**
1) **Geometry lock:** preserve craniofacial proportions from INPUT IMAGE — face outline, cheekbones, jawline/chin, inter-ocular distance, eyelid crease/eye shape, nose bridge/tip/width/length, philtrum & lip outline/fullness.  
2) **Texture lock:** keep natural **skin texture** (pores, freckles, moles, beard stubble, under-eye texture), asymmetry and tooth shade; **no beautification/AI smoothing**.  
3) **Hair lock (minimal change):** keep **hairline shape and apparent length**; only light grooming/wind and small tone shifts from lighting; **no new fringe/parting/braids/volume jumps**.  
4) **Gaze lock:** **both subjects look straight into the camera**; align pupils to the lens; preserve eyelid tension and expression; keep catchlights plausible (soft elliptical highlight ~10–11 o’clock); no cross-eye.

**What may change**
5) **Bodies only:** build natural neck/shoulders/arms/torso connecting to the fixed heads; achieve proximity/intimacy via **body pose**, not face reshaping.  
6) **Wardrobe (keep plan & colorway):**
• MOM: ivory linen blouse or light linen shirt, relaxed collar; sleeves lightly rolled to mid-forearm.
• Center child: plain cotton dress in cream/blush with short sleeves and gentle gathers.
• DAD: light beige linen button-down, collar open one button; sleeves rolled to mid-forearm; shirt untucked.

**Scene, optics & light**
7) Golden-hour meadow; sun just above horizon behind subjects; **warm rim light + soft bounced fill camera-left**; consistent shadows/occlusions on hair/shoulders.  
8) **Camera:** eye-level; lens look ≈ **85 mm FF at f/2.0–2.8**, subject distance ~2–3 m; shallow DOF, creamy bokeh.  
9) **Framing:** knee-up. Keep order as in INPUT IMAGE.

**Avoid (hard)**
Resculpted faces; changed face width/eye size/lip shape; altered hair **length or hairline**; different people; heavy skin smoothing; CGI/illustration look; multi-panel/text.
"""
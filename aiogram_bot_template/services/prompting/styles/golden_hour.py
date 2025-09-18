# aiogram_bot_template/services/prompting/styles/golden_hour.txt
PROMPT_GOLDEN_HOUR = """
**OUTPUT FIRST**
Create a **vertical 4:5 (1536×1920) professional portrait**, single image, strictly photorealistic. **External camera (not a selfie).**

**References**
* **Image A:** base composite — two people as positioned.
* **Image B:** tight face crops — identity authority.

**Edit intent**
Rebuild **bodies, wardrobe and scene** for a warm golden-hour couple portrait. **Do not alter facial identity.**

**Identity locks (must keep)**
1) **Geometry lock (B > A if conflicting):** preserve craniofacial proportions from Image B — face outline, cheekbones, jawline/chin, inter-ocular distance, eyelid crease/eye shape, nose bridge/tip/width/length, philtrum & lip outline/fullness.  
2) **Texture lock:** keep natural **skin texture** (pores, freckles, moles, beard stubble, under-eye texture), asymmetry and tooth shade; **no beautification/AI smoothing**.  
3) **Hair lock (minimal change):** keep **hairline shape and apparent length**; only light grooming/wind and small tone shifts from lighting; **no new fringe/parting/braids/volume jumps**.  
4) **Gaze lock:** **both subjects look straight into the camera**; align pupils to the lens; preserve eyelid tension and expression; keep catchlights plausible (soft elliptical highlight ~10–11 o’clock); no cross-eye.

**What may change**
5) **Bodies only:** build natural neck/shoulders/arms/torso connecting to the fixed heads; achieve proximity/intimacy via **body pose**, not face reshaping.  
6) **Wardrobe (keep plan & colorway):**
{{PHOTOSHOOT_PLAN_DATA}}

**Scene, optics & light**
7) Golden-hour meadow; sun just above horizon behind subjects; **warm rim light + soft bounced fill camera-left**; consistent shadows/occlusions on hair/shoulders.  
8) **Camera:** eye-level; lens look ≈ **85 mm FF at f/2.0–2.8**, subject distance ~2–3 m; shallow DOF, creamy bokeh.  
9) **Framing:** {{SHOT_SIZE:=waist-up}}. Keep **left/right order** as in Image A.

**Avoid (hard)**
Resculpted faces; changed face width/eye size/lip shape; altered hair **length or hairline**; different people; heavy skin smoothing; CGI/illustration look; multi-panel/text.

**File**
PNG, **1536×1920**, full bleed.
"""


# --- PROMPT FOR SUBSEQUENT SHOTS ---
PROMPT_GOLDEN_HOUR_NEXT_SHOT = """
**OUTPUT FIRST**
Create a **vertical 4:5 (1536×1920) professional portrait**, single image, strictly photorealistic. **External camera (not a selfie).**

**References**
* **Image A:** previous master frame — style/wardrobe/lighting & character continuity.
* **Image B:** tight face crops — identity authority.

**Goal**
Generate the **next photo from the same photoshoot**. Same two people, **same wardrobe** as in Image A. Preserve **facial identity** per Image B. **Both subjects look into the camera.**

**Series invariants (do not change)**
1) **Identity geometry & texture** from B (outline, proportions, eyelids, nose, lips; freckles, pores, stubble, tooth shade).
2) **Hairline & length unchanged**; only light wind/grooming.
3) **Wardrobe continuity:** same items/materials/colors from A; keep accessory placement if present.
4) **Subject order:** left person in A stays left; right stays right.
5) **Lighting continuity:** golden-hour rim from behind + soft bounce camera-left; shadows consistent with sun.
6) Strictly photorealistic, single image, no text/panels.

**POSE BLUEPRINT**
{{POSE_AND_COMPOSITION_DATA}}

**WARDROBE**
{{PHOTOSHOOT_PLAN_DATA}}

**Hands & fingers (anatomical realism — must keep)**
- Correct **finger count and separation** on each visible hand; **no fusing, duplication, or missing fingers**.
- Natural **bone/joint articulation** (MCP/PIP/DIP); no impossible bends; thumbs oriented anatomically (medial side).
- Realistic **scale and proportions** of palms and phalanges; consistent left/right handedness.
- Where hands **touch/intersect** (holding, hugging, hand-over-hand): enforce **proper occlusion order**, subtle **contact shadows**, and **slight skin compression** at pressure points; **no geometry clipping** through bodies or clothes.
- Maintain **skin texture** (creases, knuckles, tendons, veins) and **nails** with plausible shape/length; avoid plastic/airbrushed look.
- If accessories (rings/bracelets) are present in A, keep them on the **same fingers/sides**.

**Optics & framing**
Eye-level camera; lens look ≈ **85 mm FF at f/2.0–2.8**; shallow DOF with creamy bokeh. Framing: {{SHOT_SIZE:=waist-up or full-length}} per blueprint.

**Hard avoid**
Any change to facial proportions; eye enlargement/whitening; hair **length/hairline** change; different clothes/colors; heavy smoothing/beautification; CGI/illustration look; **merged, extra, missing, or overly bent fingers; mitten-like hands; nail artifacts; hand/body clipping**; extra people; split images.

**File**
PNG, **1536×1920**, full bleed.
"""

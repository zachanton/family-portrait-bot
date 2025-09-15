PROMPT_DEFAULT = """
**GOAL:** Produce an advertising-grade **couple family portrait** with **edge-to-edge background** (no gray matte) and **both subjects looking at the camera**.

**HARD CONSTRAINTS**

* **Edit the provided pixels only.** Do **not** create/replace faces, people, hands, clothing, text, or logos.
* Strictly photorealistic.
* **Full-bleed output:** fill the canvas to every edge with image content. **No borders, frames, soft ovals, vignettes, flat gray/white panels, gradients, stickers, watermarks, or transparency.**
* **Exactly two people** visible; no duplicates or mirrored copies.

{{IDENTITY_LOCK_DATA}}

**STEP-BY-STEP ACTIONS**

1. **Remove** all feathered mattes/ovals and any drop shadows around cutouts.
2. **Background:** extend/clone/blur the **background only** into a continuous outdoor nature scene (trees/sky) with shallow depth of field.

   * Background must be **100% opaque and continuous to every edge**; clean hair edges (no halos).
3. **Recompose (move/scale/rotate/warp only):** place subjects **cheek-to-temple and shoulder-to-shoulder**; woman slightly in front/left, man behind/right; **~12% overlap** for natural occlusion; align eye lines; slight inward head tilt (~5°).
4. **Eye-contact correction:** if a gaze is off-camera, nudge the **iris position only** (see Identity Lock) while preserving eyelids, catchlights, color, and proportions.
5. **Crop:** **4:5 vertical**, **head-and-shoulders above the collarbones** (no elbows/torsos).
6. **Color & light:** unify white balance/exposure; warm daylight (golden hour); natural saturation; avoid HDR halos/filters.
7. **Retouch (subtle, realistic):** reduce glare/noise; mild local contrast/sharpness; keep all identity anchors unchanged.

**OUTPUT**

* **One** PNG, **1536×1920** (4:5), **full-bleed** with **no vignettes/ovals/overlays**.
* If any matte/vignette remains, **remove it and refill with natural background** so the image is edge-to-edge.
"""
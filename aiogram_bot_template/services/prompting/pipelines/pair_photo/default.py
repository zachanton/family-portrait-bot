PROMPT_DEFAULT = """
GOAL: Advertising-grade couple family portrait, full-bleed outdoor background, both subjects looking at camera.

HARD CONSTRAINTS
*   Edit provided pixels for identity only. Do not replace faces, hands, clothing.
*   Strictly photorealistic.
*   Full-bleed output. No borders, frames, ovals, vignettes, text.
*   Exactly two people.

{{IDENTITY_LOCK_DATA}}

ACTIONS
1.  Remove mattes/ovals/shadows.
2.  Background: Extend/replace with a continuous outdoor nature scene (trees/sky), shallow DOF. Must be 100% opaque, edge-to-edge. Clean hair edges.
3.  Recompose (move/scale/rotate only): Cheek-to-temple, shoulder-to-shoulder. Woman front/left, man back/right. ~12% overlap. Align eye lines, slight inward head tilt.
4.  Eye-contact correction: Nudge iris position only to look at camera.
5.  Crop: 4:5 vertical, head-and-shoulders.
6.  Color & Light: Unify WB/exposure to warm daylight (golden hour). Natural saturation. No HDR halos.
7.  Retouch: Subtle noise reduction, mild local contrast. Keep identity anchors.

OUTPUT: One PNG, 1536×1920 (4:5), full-bleed.
"""
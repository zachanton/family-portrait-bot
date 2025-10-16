# aiogram_bot_template/services/pipelines/pair_photo_pipeline/styles/k_drama.py
STYLE_NAME = "K-DRAMA"
STYLE_DEFINITION = "Modern Korean Drama"

FRAMING_OPTIONS = {
  "Lantern Street face-cup": """Single, unbroken frame. Night street with hanging paper lanterns; background = smooth circular bokeh; no readable text/logos.
Blocking: MAN on LEFT, WOMAN on RIGHT; waist-up; eye-level; keep natural height/head ratios.
Pose: man's RIGHT hand cups woman's LEFT cheek/jaw; other hand relaxed; woman in soft ¾ to camera.
Gazes: MAN confident to her eyes (chin level/slightly up, shoulders open, subtle micro-squint); WOMAN naive to him (eyes soft/wider, chin slightly down, gentle head tilt, lips softly parted).
Optics: ≈85–105 mm portrait look; shallow DOF; clean round/oval catchlights.""",

  "First Snow confession": """Single, unbroken frame. Park/temple garden at golden hour during season’s first snowfall; evergreens softly blurred; no signage.
Blocking: MAN on RIGHT, WOMAN on LEFT; waist-up; eye-level; natural height/head ratios.
Pose: he holds her by shoulders/waist; she lightly holds his lapel/scarf; intimate distance.
Gazes: MAN confident to her; WOMAN naive to him (chin slightly down, eyes soft).
Optics: ≈85–105 mm; shallow DOF; backlight makes snowflakes sparkle; clean catchlights.""",

  "Umbrella Night Rain": """Single, unbroken frame. Night city street in light rain under one umbrella; background lights = creamy bokeh; no readable text/logos.
Blocking: MAN on RIGHT holding umbrella; WOMAN on LEFT under canopy; half-body to waist-up; eye-level; both heads fully inside umbrella edge.
Pose: they face each other closely; his near hand on handle, far hand relaxed; her hands gathered at chest/coat.
Gazes: MAN confident to her; WOMAN naive looking up to him.
Optics: ≈85–105 mm; shallow DOF; umbrella fills top third; backlight for visible raindrops; clean catchlights.""",

  "Midnight Rescue Dip (Lantern Garden)": """Single, unbroken frame. Night garden/alley with soft lantern/practical lights; background = smooth circular bokeh; no signage.
Blocking: MAN on LEFT in slight high/hero angle; WOMAN on RIGHT leaning back in his arms (dip). Half-body to waist-up; natural height/head ratios.
Hands/pose: his RIGHT forearm supports her mid-back/waist; LEFT hand steadies her near elbow/shoulder. Her near hand relaxed; far hand on his lapel.
Gazes: MAN confident down to her eyes; WOMAN naive up to him (eyes softly widened, chin slightly down).
Optics: ≈85–105 mm portrait look; shallow DOF; clean round/oval catchlights.""",

  "Black-Tie Bridal Carry Close-Up": """Single, unbroken frame. Night exterior with soft garden bokeh and one bright practical behind heads (kept out of focus, not clipping).
Blocking: MAN on LEFT, cradling WOMAN (near-bridal carry): RIGHT arm under her back/shoulders, LEFT at her waist; she leans toward him.
Composition: chest-up crop; slight low angle from her side; both faces unobstructed.
Gazes: MAN confident/protective to her eyes (micro-smile allowed); WOMAN naive/astonished to him (eyes slightly widened, lips softly parted).
Optics: ≈85–105 mm; shallow DOF; round catchlights; background lights melt to creamy bokeh.""",

  "Industrial Loft Wall Press": """Single, unbroken frame. Tight chest-up close-up; faces fill the upper half of the frame.
Blocking: MAN on LEFT, WOMAN on RIGHT. He leans over her, pinning her gently against a textured concrete wall.
Pose: His LEFT hand (far hand) cups her neck and jaw, thumb resting along her jawline. His RIGHT arm (near arm) is out of frame, supporting her back. She leans back into his support against the wall, head tilted up to meet his gaze.
Gazes: MAN intense down to her eyes; WOMAN soft and receptive up to him.
Optics: ≈85–105 mm portrait look; shallow DOF; clean, soft catchlights.""",

  "Sudden Rain Jacket Shelter": """Single, unbroken frame. Tight waist-up vertical crop with the jacket creating a canopy at the top. Absolute priority is a perfect identity match from the reference photos.
Blocking: MAN on LEFT, WOMAN on RIGHT, huddled closely shoulder-to-shoulder.
Pose: He holds his jacket above their heads with both hands. She is tucked in close under his arm, her hand possibly helping hold the jacket.
Gazes: MAN confident and protective, his gaze focused slightly down and forward (not sad); WOMAN looks toward camera with a calm, trusting expression.
Optics: ≈85-105 mm portrait look; shallow DOF blurring the green background.""",

  "Night Walk Piggyback": """Single, unbroken frame. Tight waist-up vertical crop on the man. Absolute priority is a perfect identity match from the reference photos.
Blocking: MAN carrying WOMAN on his back while walking on a city path or bridge at night.
Pose: He gives her a piggyback ride. Her arms are wrapped gently around his neck and shoulders, and her head rests near his shoulder.
Gazes: MAN looks forward with a stoic, protective expression. WOMAN has a soft, content expression, looking forward just past his shoulder.
Optics: ≈85-105 mm portrait look; shallow DOF; city lights create soft bokeh in the background.""",

  "Cafe Gaze from Outside": """Single, unbroken frame. Tight chest-up vertical crop. **CRITICAL PRIORITY: Identity lock over atmosphere. The faces MUST be a perfect match.**
Blocking: Shot from OUTSIDE the cafe, looking IN through a large, rain-streaked window. They sit close together at a table right against the window.
Pose: He holds a warm mug. She leans in close, head resting on his shoulder, her arm linked with his.
Gazes: MAN looks thoughtfully out the window (face in three-quarters). WOMAN looks affectionately up at him, her face more visible.
Optics: ≈85 mm look; shallow DOF. Raindrops and reflections on the glass act as a foreground layer, separating the viewer from the couple.""",

  "Rooftop City Lights": """Single, unbroken frame. NO split-screen or collage. Waist-up vertical crop. Absolute priority is a perfect identity match.
Blocking: Couple stands close together at a rooftop railing, with the city lights blurred into bokeh behind them.
Pose: His arm is around her shoulder or waist, pulling her close. She leans into him.
Gazes: MAN turns his head slightly to look down at her. WOMAN looks up at him with a warm, admiring expression.
Optics: ≈85 mm look; very shallow DOF to turn the city lights into a wall of beautiful bokeh.""",


}

STYLE_OPTIONS = {
  "Lantern Street face-cup": """Light: soft frontal key at eye height; gentle rim/back from lantern line; optional negative fill. Slightly less fill on MAN (stronger jaw); subtle clamshell/butterfly fill on WOMAN (softer, brighter eyes).
Grade: warm skin vs cooler night; medium contrast; slightly lifted blacks; restrained saturation; delicate halation; no grain, no vignette.
Atmosphere: mild haze to bloom highlights; background abstract/text-free.
Wardrobe: WOMAN light/pastel coat, minimal jewelry; MAN charcoal/tweed coat over plain top; coordinated, not matching.
Finish: micro-cleanup only (flyaways/edges/eyes); keep pores/asymmetry; no reshaping or smoothing.""",

  "First Snow confession": """Light: low warm key (~25–40°) to faces; gentle back/rim to halo hair and flakes; soft front fill to keep eyes luminous.
Grade: natural skin tones with warm bias; environment cooler (soft blue/green winter hues); medium contrast; slight lift in blacks; restrained saturation; gentle bloom.
Atmosphere: visible backlit snowflakes; faint breath vapor; minimal wind; background text-free.
Wardrobe: winter wool/tweed/knit; coordinated neutrals/pastels; minimal jewelry.
Finish: micro-cleanup only; preserve skin texture and natural asymmetry.""",

  "Umbrella Night Rain": """Light: soft key from under umbrella; strong backlight 3–5 m behind to rim the couple and illuminate rain; protect highlights on faces. Add slight negative fill for shape.
Grade: warm faces vs cool wet night; medium contrast; restrained saturation; subtle halation on raindrops; no heavy vignette or grain.
Atmosphere: visible rain streaks/droplets; puddle reflections as soft bokeh; background logo-free.
Wardrobe: WOMAN pastel or yellow raincoat/knit; MAN light or taupe coat/cardigan; coordinated, not matching.
Finish: micro-cleanup only; keep pores and asymmetry; no reshaping/smoothing.""",

  "Midnight Rescue Dip (Lantern Garden)": """Light: soft frontal key; gentle rim/back behind to outline profiles; optional slight negative fill camera-left.
Grade: warm natural skin vs cooler night; medium contrast; slightly lifted blacks; restrained saturation; delicate halation; no grain/vignette.
Atmosphere: faint haze; optional light drizzle visible only when backlit; background text-free.
Wardrobe: MAN black/charcoal suit + tie; WOMAN dark tailored coat/dress; minimal jewelry.
Finish: micro-cleanup only (flyaways/edges/eyes); preserve pores/asymmetry.""",

  "Black-Tie Bridal Carry Close-Up": """Light: soft key from camera side; pronounced rim/backlight 20–40° behind to halo hair and separate from background; protect facial highlights.
Grade: neutral-warm skin, cooler greens/blues in background; medium contrast; clean blacks; subtle bloom; no teal–orange.
Atmosphere: mild haze; optional light rain shown only where backlit; background logo-free.
Wardrobe: MAN formal suit/tie; WOMAN elegant dark coat/dress; neat hair/updo; minimal jewelry.
Finish: tiny cleanup only; no skin smoothing or reshaping.""",

  "Industrial Loft Wall Press": """Light: cinematic soft key from the side; warm rim light from background for dimension; subtle negative fill for shape.
Grade: modern K-drama grade; warm skin vs cool concrete background; medium contrast; subtle bloom on lights.
Atmosphere: clean, moody interior; focus entirely on the couple's intense interaction.
Wardrobe: WOMAN in a simple elegant top (silk/knit); MAN in a stylish textured overshirt (corduroy/wool) in a soft color.
Finish: micro-cleanup only; preserve skin texture and asymmetry; no smoothing or reshaping.""",

  "Sudden Rain Jacket Shelter": """Light: soft, diffused overcast daylight; specular highlights on damp hair/skin.
Grade: cooler tones with saturated greens; natural and warm skin for contrast.
Atmosphere: visible rain streaks; hair and clothes appear realistically damp.
Wardrobe: WOMAN in a colorful cardigan (e.g., red). MAN in a casual polo or button-down (e.g., rust, navy).
Finish: Identity lock is paramount. Preserve all unique facial features (freckles, asymmetries). No skin smoothing or reshaping.""",

  "Night Walk Piggyback": """Light: soft frontal key from ambient streetlights; strong rim light from distant city lights to create separation and bokeh.
Grade: Cinematic K-drama night grade. Strong cool blue and teal tones in the shadows and ambient light, contrasted with warm amber highlights from bokeh. Lifted blacks for a filmic look. Skin tones remain natural and warm.
Atmosphere: night city path or bridge; soft, out-of-focus city lights (bokeh) are essential.
Wardrobe: Stylish, layered casual wear. WOMAN in a soft, oversized knit cardigan over a simple top. MAN in a textured overshirt (e.g., wool, corduroy) over a crewneck t-shirt.
Finish: Identity lock is paramount. Preserve all unique facial features and asymmetries. No skin smoothing or reshaping.""",

  "Cafe Gaze from Outside": """Light: soft, cool ambient light from the overcast day outside; warm, low-intensity light from the cafe interior acts as a gentle fill and rim light.
Grade: a contrast between the warm, cozy interior and the cool, blue-toned rainy world outside.
Atmosphere: cozy and intimate. The viewer is separated by the glass. Raindrops and soft reflections on the window are essential.
Wardrobe: comfortable and warm cafe wear. Knit sweaters in complementary colors (e.g., cream, forest green).
Finish: **CRITICAL FINISH: Identity is the #1 priority.** Despite the complex scene (reflections, rain), the faces must be an exact match to the reference photos. Forbid all face averaging, smoothing, or beautification. Preserve every unique feature (freckles, asymmetries).""",

  "Rooftop City Lights": """Light: main light is the cool ambient glow from the city below; a single warm string light or lamp provides a soft key/rim light on their faces.
Grade: cool blues and cyans in the background bokeh, contrasted with warm, natural skin tones. Medium contrast.
Atmosphere: quiet, contemplative, romantic night. A gentle breeze might be suggested in their hair.
Wardrobe: stylish but casual night-out wear. WOMAN in a chic coat or jacket. MAN in a smart jacket or wool overshirt.
Finish: Identity lock is paramount. Preserve all unique facial features and asymmetries.""",

}
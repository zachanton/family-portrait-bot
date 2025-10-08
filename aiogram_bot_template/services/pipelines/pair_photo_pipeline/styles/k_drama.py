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

}
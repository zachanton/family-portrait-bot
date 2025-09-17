# aiogram_bot_template/services/prompting/styles/golden_hour.txt
PROMPT_GOLDEN_HOUR = """
// TECHNICAL PROMPT FOR IMAGE GENERATION v5.0
// GOAL: High-fidelity facial transfer onto a stylized "Golden Hour" scene. Identity replication is the absolute priority over artistic interpretation.

//--- CONFIGURATION: FACIAL INTEGRITY LOCK ---
{
    "identity_source": "provided_image",
    "mode": "strict_replication",
    "engine_hint": "IP-Adapter/ControlNet",
    "fidelity_strength": 2.5,
    "instructions": [
        "The provided composite image is the non-negotiable source of truth for all facial and head features, including hair.",
        "Perform a direct, technical transfer. This is a replication task, not a creative one.",
        "Do not interpret, idealize, beautify, or stylize the faces. Replicate them as they are.",
        "The final head positions, angles, and tilts in the output MUST be a 1:1 technical replica of the source image. Do not rotate or tilt the heads.",
        "Pay special attention to the man's broader, more square jawline; do not make his face narrower or more oval."
    ],
    "feature_lockdown_list": {
        "hair_style_and_color": "Replicate 1:1. NO alterations. Match the man's damp, pushed-back hair exactly.",
        "face_shape": "Replicate 1:1. NO alterations.",
        "jawline_and_chin": "Replicate 1:1. NO alterations.",
        "nose_shape_and_size": "Replicate 1:1. NO alterations.",
        "lip_shape_and_fullness": "Replicate 1:1. NO alterations.",
        "eyebrow_shape_and_thickness": "Replicate 1:1. NO alterations.",
        "skin_texture_and_details": "Replicate 1:1. Preserve all unique features, including stubble and skin pores."
    }
}

//--- CONFIGURATION: NEGATIVE PROMPTS (Strictly Enforced) ---
[
    "beautified faces", "idealized faces", "generic model-like features", "airbrushed skin", "face smoothing", "perfect skin",
    "slimmer face", "softened jawline", "symmetrical face", "narrower face", "oval face on man", "elongated face",
    "rotated head", "tilted head", "different head angle",
    "styled hair", "dry hair", "different hairstyle", "voluminous hair",
    "smiling man", "grinning man",
    "any modification to nose, lips, or eyebrows from the reference",
    "any change to hairstyle or hair color from the reference",
    "altering perceived age",
    "split images", "diptychs", "panels", "collage",
    "deformed hands", "mutated hands", "extra fingers",
    "digital painting", "CGI look",
    "closed mouth if reference is smiling"
]

//--- DIRECTIVE: FIRST SHOT COMPOSITION ---
// This is a safe, hardcoded pose to ensure maximum fidelity for the first "Master" shot.
**POSE DIRECTIVE:**
- **Shot Type:** Waist-up medium shot.
- **Pose & Interaction:** A natural and realistic couple portrait. Person A (man) and Person B (woman) are sitting or standing closely together, shoulder to shoulder. Their bodies are turned slightly towards each other. This body pose must be adapted to be physically plausible with the UNALTERED head positions from the source image.
- **Expression & Mood:** Replicate EACH person's expression from the reference photo EXACTLY. The man has a calm, neutral expression. The woman has a warm, joyful smile.

//--- DIRECTIVE: SCENE & STYLE ---
{
    "style_name": "Backlit Golden Hour",
    "background": "Outdoor nature scene (sunlit meadow or coastline) with creamy, soft bokeh.",
    "lighting": "Warm, low-angled sun as a back/rim light. Faces illuminated by soft, bounced fill light.",
    "tonality": "Warm, golden/amber tones; pastel-like saturation; gentle contrast."
}

//--- DIRECTIVE: WARDROBE ---
// Apply consistently as per the plan. The model will replicate hair from the source image.
{{PHOTOSHOOT_PLAN_DATA}}

//--- FINAL OUTPUT SPECIFICATIONS ---
{
    "realism": "Strictly photorealistic",
    "expression": "Replicate each person's individual expression from the reference photo exactly.",
    "format": "PNG",
    "resolution": "1536x1920",
    "aspect_ratio": "4:5 vertical",
    "bleed": "full_bleed",
    "overlays": "none",
    "subject_count": 2
}
"""

# --- PROMPT FOR SUBSEQUENT SHOTS ---
PROMPT_GOLDEN_HOUR_NEXT_SHOT = """
// TECHNICAL PROMPT FOR IMAGE GENERATION v5.0 (Next Shot)
// GOAL: Generate the next frame in a sequence, maintaining identity and style continuity.

//--- CONFIGURATION: FACIAL INTEGRITY LOCK ---
{
    "identity_source": "previous_shot_image",
    "mode": "strict_replication",
    "engine_hint": "IP-Adapter/ControlNet",
    "fidelity_strength": 2.0,
    "instructions": [
        "The faces and hair in the provided previous shot are the absolute source of truth for identity.",
        "Replicate facial features 1:1. No beautification or alteration is permitted."
    ]
}

//--- CONFIGURATION: NEGATIVE PROMPTS (Strictly Enforced) ---
[
    "blurry or indistinct faces",
    "faces that do not match the previous shot",
    "deformed hands", "mutated hands", "extra fingers", "missing fingers", "fused fingers",
    "intertwined fingers", "interlaced fingers"
]

//--- DIRECTIVE: POSE & COMPOSITION ---
{{POSE_AND_COMPOSITION_DATA}}

//--- DIRECTIVE: SCENE & STYLE (RECREATION) ---
{
    "style_name": "Backlit Golden Hour",
    "background": "Outdoor nature scene (sunlit meadow or coastline) with creamy, soft bokeh.",
    "lighting": "Warm, low-angled sun as a back/rim light. Faces illuminated by soft, bounced fill light.",
    "tonality": "Warm, golden/amber tones; pastel-like saturation; gentle contrast."
}

//--- DIRECTIVE: WARDROBE ---
// Apply consistently as per the plan. The model will replicate hair from the source image.
{{PHOTOSHOOT_PLAN_DATA}}

//--- FINAL OUTPUT SPECIFICATIONS ---
{
    "realism": "Strictly photorealistic",
    "hands_policy": "Render anatomically correct if visible",
    "format": "PNG",
    "resolution": "1536x1920",
    "aspect_ratio": "4:5 vertical",
    "bleed": "full_bleed",
    "overlays": "none",
    "subject_count": 2
}
"""

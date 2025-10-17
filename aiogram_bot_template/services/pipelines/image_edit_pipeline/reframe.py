# aiogram_bot_template/services/pipelines/image_edit_pipeline/reframe.py

PROMPT_IMAGE_REFRAME = """
TASK: Reframe the input image to a new aspect ratio: {{ASPECT_RATIO}}. This is an outpainting or inpainting task.

CRITICAL RULES:
1.  **Identity and Content Preservation:** You MUST perfectly preserve the facial identity, features, structure, pose, expression, and all existing content of the person/people in the original image. DO NOT CHANGE a single detail of the original content.
2.  **Seamless Extension:** Plausibly and photorealistically extend the scene, background, and clothing to fill the new {{ASPECT_RATIO}} canvas. The transition between the original image and the newly generated parts must be invisible.
3.  **Style Consistency:** Maintain the original image's style, lighting, color grading, and overall mood.
4.  **No Artifacts:** Do not add text, watermarks, logos, or strange visual artifacts.
5.  **Single Output:** Output a single, edited, full-bleed image in the target aspect ratio.
"""

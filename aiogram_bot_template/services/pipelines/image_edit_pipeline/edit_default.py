# aiogram_bot_template/services/pipelines/image_edit_pipeline/edit_default.py

PROMPT_IMAGE_EDIT_DEFAULT = """
TASK: Edit the input image based on the text instruction provided by the user.

USER INSTRUCTION:
"{{USER_PROMPT}}"

CRITICAL RULES:
1.  **Identity Preservation:** You MUST preserve the facial identity, features, and structure of the person/people in the original image. The result should look like the same person, but with the requested changes.
2.  **Photorealism:** The edit must be subtle, seamless, and maintain a high level of photorealism.
3.  **Style Consistency:** Maintain the original image's style, lighting, composition, and overall mood unless the user specifically asks to change it.
4.  **No Artifacts:** Do not add text, watermarks, logos, or strange visual artifacts.
5.  **Single Output:** Output a single, edited, full-bleed image.
"""
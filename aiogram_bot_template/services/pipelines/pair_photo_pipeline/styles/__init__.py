# aiogram_bot_template/services/pipelines/pair_photo_pipeline/styles/__init__.py
"""
Style registry for the pair photo pipeline.

This module dynamically discovers and registers all available style modules
within this directory. Each style should have its own .py file.

To add a new style:
1. Create a new .py file in this directory (e.g., 'new_style.py').
   It must define STYLE_NAME, STYLE_DEFINITION, FRAMING_OPTIONS, and STYLE_OPTIONS.
2. Add a corresponding preview image to `aiogram_bot_template/assets/style_previews/`.
   The image name should match the style's ID key (e.g., 'new_style.jpg').
3. Add the style to the `STYLES` dictionary below, following the existing pattern.
"""
from . import k_drama
from . import retro_motel

# The central registry of all available styles.
# The keys ('k_drama', 'retro_motel') are used as unique identifiers and
# should match the preview image filenames (without extension).
STYLES = {
    "k_drama": {
        "name": k_drama.STYLE_NAME,
        "module": k_drama,
        "preview_image": "k_drama.png",
    },
    "retro_motel": {
        "name": retro_motel.STYLE_NAME,
        "module": retro_motel,
        "preview_image": "retro_motel.png",
    },
    # To add a new style, uncomment and configure the following:
    # "new_style_id": {
    #     "name": new_style.STYLE_NAME,
    #     "module": new_style,
    #     "preview_image": "new_style_id.jpg",
    # },
}
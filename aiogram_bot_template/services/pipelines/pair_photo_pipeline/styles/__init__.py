# aiogram_bot_template/services/pipelines/pair_photo_pipeline/styles/__init__.py
from . import k_drama
from . import retro_motel

# A registry of available styles.
# The key is the 'style_id' used internally.
# 'name' is the user-facing text for the button.
# 'module' is the imported style module containing FRAMING and STYLE dicts.
STYLES = {
    "k_drama": {
        "name": "🇰🇷 K-Drama Romance",
        "module": k_drama,
    },
    "retro_motel": {
        "name": " 🎬 Retro Motel Pastel",
        "module": retro_motel,
    },
    # To add a new style:
    # 1. Create a new file, e.g., 'noir_film.py' in this directory.
    # 2. Add FRAMING and STYLE dictionaries to it.
    # 3. Import it here: from . import noir_film
    # 4. Add it to this STYLES dict: "noir_film": {"name": "Noir Film 🎞️", "module": noir_film}
}
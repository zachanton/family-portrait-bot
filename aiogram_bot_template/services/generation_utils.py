# aiogram_bot_template/services/generation_utils.py
from aiogram.utils.i18n import gettext as _

from aiogram_bot_template.keyboards.inline.quality import QUALITY


def create_generation_caption(user_data: dict) -> str:
    """
    Creates a caption for the generated image based on user data.

    Returns:
        A formatted string for the image caption.
    """
    quality_name = _(QUALITY.get(user_data["quality"], "Unknown"))
    base_caption = _("Your request: «{prompt}» (quality: {quality}).").format(
        prompt=user_data["prompt"], quality=quality_name
    )
    return _("Done! {base_caption}").format(base_caption=base_caption)

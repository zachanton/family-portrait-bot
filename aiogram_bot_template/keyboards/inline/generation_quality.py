# aiogram_bot_template/keyboards/inline/generation_quality.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.i18n import gettext as _
from aiogram_bot_template.data.settings import settings
from aiogram_bot_template.data.constants import GenerationType
from .callbacks import BackToPromptSelection, ReturnToMainMenu
from aiogram_bot_template.keyboards.inline.quality import _get_translated_quality_name


def generation_quality_kb(
    is_trial_available: bool,
    generation_type: GenerationType,
    *,
    continue_key: str | None = None,
    request_id: int | None = None,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []

    # Dynamically get the correct settings section for the given generation type
    generation_config = getattr(settings, generation_type.value, settings.child_generation)

    if is_trial_available:
        rows.append([
            InlineKeyboardButton(
                text=_("🎁 Free Trial"), callback_data="quality:0"
            )
        ])

    for q, tier in sorted(generation_config.tiers.items()):
        if q == 0:
            continue
        stars = "💎" * q
        quality_name = _get_translated_quality_name(q)
        label = f"{stars} {quality_name}  •  {tier.price} ⭐"
        rows.append([InlineKeyboardButton(text=label, callback_data=f"quality:{q}")])

    back_button: InlineKeyboardButton
    if continue_key and request_id:
        # If we are in the "retry" flow, return to the main "next step" menu
        back_button = InlineKeyboardButton(
            text=_("⬅️ Back to Options"),
            callback_data=ReturnToMainMenu(key=continue_key, request_id=request_id).pack(),
        )
    else:
        # If this is the first generation, return to the age/gender selection
        back_button = InlineKeyboardButton(
            text=_("⬅️ Back to Options"),
            callback_data=BackToPromptSelection(is_child_gen=True).pack()
        )
    rows.append([back_button])

    return InlineKeyboardMarkup(inline_keyboard=rows)

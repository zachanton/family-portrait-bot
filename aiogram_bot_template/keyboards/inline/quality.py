# aiogram_bot_template/keyboards/inline/quality.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.i18n import gettext as _
from aiogram_bot_template.data.settings import settings
from .callbacks import BackToPromptSelection
from .callbacks import ReturnToMainMenu


def _get_translated_quality_name(q: int) -> str:
    """Returns a translatable string for a given quality tier."""
    if q == 0:
        return _("Trial")
    if q == 1:
        return _("Standard")
    if q == 2:
        return _("Enhanced")
    if q == 3:
        return _("Premium")
    return _("Unknown")


def quality_kb(
    is_trial_available: bool,
    continue_key: str | None = None,
    request_id: int | None = None,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []

    if is_trial_available:
        rows.append([
            InlineKeyboardButton(
                text=_("🎁 Free Trial"), callback_data="quality:0"
            )
        ])

    for q, tier in sorted(settings.image_edit.tiers.items()):
        if q == 0:
            continue
        stars = "💎" * q
        quality_name = _get_translated_quality_name(q)
        label = f"{stars} {quality_name}  •  {tier.price} ⭐"
        rows.append([InlineKeyboardButton(text=label, callback_data=f"quality:{q}")])

    back_button = None
    if continue_key and request_id:
        # If there is context, return to the main "next step" menu
        back_button = InlineKeyboardButton(
            text=_("⬅️ Back to Options"),
            callback_data=ReturnToMainMenu(key=continue_key, request_id=request_id).pack(),
        )
    else:
        # If this is the first generation, return to the prompt input
        back_button = InlineKeyboardButton(
            text=_("⬅️ Back to Options"),
            callback_data=BackToPromptSelection().pack()
        )
    rows.append([back_button])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def upscale_quality_kb(is_trial_available: bool, continue_key: str, request_id: int) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []

    if is_trial_available:
        rows.append([
            InlineKeyboardButton(
                text=_("🎁 Free Trial"), callback_data="quality:0"
            )
        ])

    for q, tier in sorted(settings.upscale.tiers.items()):
        if q == 0:
            continue
        stars = "💎" * q
        quality_name = _get_translated_quality_name(q)
        label = f"{stars} {quality_name}  •  {tier.price} ⭐"
        rows.append([InlineKeyboardButton(text=label, callback_data=f"quality:{q}")])

    rows.append(
        [
            InlineKeyboardButton(
                text=_("⬅️ Back to Options"),
                callback_data=ReturnToMainMenu(
                    key=continue_key, request_id=request_id
                ).pack(),
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)
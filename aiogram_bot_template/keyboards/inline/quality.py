# aiogram_bot_template/keyboards/inline/quality.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.i18n import gettext as _, ngettext
from aiogram_bot_template.data.settings import settings

def _get_translated_tier_name(q: int, count: int) -> str:
    """Returns a translatable string for a given quality tier."""
    if q == 0:
        # Use ngettext for proper pluralization on the free tier as well
        return ngettext(
            "🎁 Free Trial ({count} Portrait)",
            "🎁 Free Trial ({count} Portraits)",
            count
        ).format(count=count)
    
    # Using ngettext for proper pluralization
    return ngettext(
        "✨ {count} Random Portrait",
        "✨ {count} Random Portraits",
        count
    ).format(count=count)

def quality_kb(is_trial_available: bool) -> InlineKeyboardMarkup:
    """
    Creates a keyboard for selecting a generation package.
    Conditionally shows the Tier 0 (Free Trial) button.
    """
    rows: list[list[InlineKeyboardButton]] = []

    for q, tier in sorted(settings.group_photo.tiers.items()):
        
        if q == 0:
            if not is_trial_available:
                continue
            # Pass the count to the translation function
            label = _get_translated_tier_name(q, tier.count)
            rows.append([InlineKeyboardButton(text=label, callback_data=f"quality:{q}")])
        else:
            tier_name = _get_translated_tier_name(q, tier.count)
            label = f"{tier_name}  •  {tier.price} ⭐"
            rows.append([InlineKeyboardButton(text=label, callback_data=f"quality:{q}")])
    
    return InlineKeyboardMarkup(inline_keyboard=rows)
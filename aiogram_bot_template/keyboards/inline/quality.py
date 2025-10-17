# aiogram_bot_template/keyboards/inline/quality.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.i18n import gettext as _, ngettext

from aiogram_bot_template.data.constants import GenerationType
from aiogram_bot_template.data.settings import settings

def _get_translated_tier_name(q: int, count: int) -> str:
    """Returns a translatable string for a given quality tier."""
    if q == 0:
        return ngettext(
            "🎁 Free Trial ({count} Portrait)",
            "🎁 Free Trial ({count} Portraits)",
            count
        ).format(count=count)
    
    # Using a more appealing name like "Studio Portrait"
    return ngettext(
        "✨ {count} Studio Portrait",
        "✨ {count} Studio Portraits",
        count
    ).format(count=count)

def quality_kb(
    generation_type: GenerationType, 
    is_trial_available: bool,
    is_live_queue_available: bool
) -> InlineKeyboardMarkup:
    """
    Creates a keyboard for selecting a generation package.
    Dynamically loads tiers and conditionally shows special options.
    """
    rows: list[list[InlineKeyboardButton]] = []
    
    try:
        generation_config = getattr(settings, generation_type.value)
    except AttributeError:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=_("Error: Tiers not configured"), callback_data="config_error")]
        ])

    # Tier 0 (Free Trial) is handled first
    if is_trial_available and 0 in generation_config.tiers:
        tier_0 = generation_config.tiers[0]
        label = _get_translated_tier_name(0, tier_0.count)
        rows.append([InlineKeyboardButton(text=label, callback_data="quality:0")])
        
    # Tier 1 (Live Queue) button with more context
    if is_live_queue_available and 1 in generation_config.tiers:
        label = _("🕒 Join the Live Queue (Free & Public)")
        rows.append([InlineKeyboardButton(text=label, callback_data="quality:1")])

    # Loop for paid tiers (q > 1)
    for q, tier in sorted(generation_config.tiers.items()):
        if q > 1: # Only show paid tiers here
            tier_name = _get_translated_tier_name(q, tier.count)
            label = f"{tier_name}  •  {tier.price} ⭐"
            rows.append([InlineKeyboardButton(text=label, callback_data=f"quality:{q}")])
    
    return InlineKeyboardMarkup(inline_keyboard=rows)
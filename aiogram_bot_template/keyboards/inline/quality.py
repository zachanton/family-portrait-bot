# aiogram_bot_template/keyboards/inline/quality.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.i18n import gettext as _, ngettext

# --- NEW: Import GenerationType to know which settings to use ---
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
    
    return ngettext(
        "✨ {count} Portrait",
        "✨ {count} Portraits",
        count
    ).format(count=count)

# --- REFACTORED: The function now accepts a generation_type ---
def quality_kb(generation_type: GenerationType, is_trial_available: bool) -> InlineKeyboardMarkup:
    """
    Creates a keyboard for selecting a generation package.
    Dynamically loads tiers based on the provided generation_type.
    Conditionally shows the Tier 0 (Free Trial) button.
    """
    rows: list[list[InlineKeyboardButton]] = []
    
    # --- DYNAMIC LOGIC: Get the correct config section (e.g., settings.child_generation) ---
    try:
        generation_config = getattr(settings, generation_type.value)
    except AttributeError:
        # Fallback or error handling if the config section doesn't exist
        # This prevents the bot from crashing on a config error.
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=_("Error: Tiers not configured"), callback_data="config_error")]
        ])

    for q, tier in sorted(generation_config.tiers.items()):
        
        if q == 0:
            if not is_trial_available:
                continue
            label = _get_translated_tier_name(q, tier.count)
            rows.append([InlineKeyboardButton(text=label, callback_data=f"quality:{q}")])
        else:
            tier_name = _get_translated_tier_name(q, tier.count)
            label = f"{tier_name}  •  {tier.price} ⭐"
            rows.append([InlineKeyboardButton(text=label, callback_data=f"quality:{q}")])
    
    return InlineKeyboardMarkup(inline_keyboard=rows)
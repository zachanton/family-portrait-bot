# aiogram_bot_template/keyboards/inline/quality.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.i18n import gettext as _
from aiogram_bot_template.data.settings import settings

def _get_translated_quality_name(q: int) -> str:
    """Returns a translatable string for a given quality tier."""
    # --- ИЗМЕНЕНИЕ: Теперь `q=0` всегда корректно называется "Free Trial" ---
    if q == 0:
        return _("Free Trial")
    if q == 1:
        return _("Standard")
    if q == 2:
        return _("Enhanced")
    if q == 3:
        return _("Premium")
    return _("Unknown")


def quality_kb(is_trial_available: bool) -> InlineKeyboardMarkup:
    """
    Creates a keyboard for quality selection based on settings.
    Conditionally shows the Tier 0 (Free Trial) button.
    """
    rows: list[list[InlineKeyboardButton]] = []

    # --- ИЗМЕНЕНИЕ: ЕДИНЫЙ ЦИКЛ для всех тиров, который решает проблему дублирования ---
    for q, tier in sorted(settings.group_photo.tiers.items()):
        
        # Логика для бесплатного тира (q=0)
        if q == 0:
            # Если бесплатная попытка недоступна, просто пропускаем этот тир
            if not is_trial_available:
                continue
            
            # Если доступна, создаем красивую кнопку без цены
            label = f"🎁 {_get_translated_quality_name(q)}"
            rows.append([InlineKeyboardButton(text=label, callback_data=f"quality:{q}")])
        
        # Логика для всех платных тиров (q > 0)
        else:
            stars = "💎" * q
            quality_name = _get_translated_quality_name(q)
            label = f"{stars} {quality_name}  •  {tier.price} ⭐"
            rows.append([InlineKeyboardButton(text=label, callback_data=f"quality:{q}")])
    
    return InlineKeyboardMarkup(inline_keyboard=rows)
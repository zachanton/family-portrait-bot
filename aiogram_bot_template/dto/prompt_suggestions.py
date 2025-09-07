# aiogram_bot_template/dto/prompt_suggestions.py
from pydantic import BaseModel
from typing import Any


class PromptSuggestion(BaseModel):
    """Defines a structure for a single, predefined edit suggestion."""
    emoji: str
    text: str  # User-facing text for the button, e.g., "Change Eye Color to Green"
    prompt_for_enhancer: str  # The simple, clear instruction for the LLM enhancer


# 1. SINGLE SOURCE OF TRUTH: All suggestion data is now in this flat dictionary.
#    Prompts are now simple instructions for the enhancer service.
ALL_PROMPT_SUGGESTIONS: dict[str, PromptSuggestion] = {
    # Eyes
    "eyes_green": PromptSuggestion(emoji="🍃", text="Change Eye Color to Green", prompt_for_enhancer="Change the eye color to a natural green."),
    "eyes_blue": PromptSuggestion(emoji="🌊", text="Change Eye Color to Blue", prompt_for_enhancer="Change the eye color to a natural blue."),
    "eyes_brown": PromptSuggestion(emoji="🌰", text="Change Eye Color to Brown", prompt_for_enhancer="Change the eye color to a natural brown."),
    "eyes_hazel": PromptSuggestion(emoji="🍂", text="Change Eye Color to Hazel", prompt_for_enhancer="Change the eye color to a natural hazel (blend of brown and green)."),

    # Hair Tone
    "hair_lighter": PromptSuggestion(emoji="☀️", text="Lighten Hair Color", prompt_for_enhancer="Make the hair color one shade lighter, as if sun-kissed."),
    "hair_darker": PromptSuggestion(emoji="🌙", text="Darken Hair Color", prompt_for_enhancer="Make the hair color one shade darker."),

    # Hair Length
    "hair_short": PromptSuggestion(emoji="✂️", text="Give a Short Hairstyle", prompt_for_enhancer="Make the hair noticeably shorter, like a fresh trim of the current style."),
    "hair_long": PromptSuggestion(emoji="✨", text="Give a Long Hairstyle", prompt_for_enhancer="Make the hair noticeably longer, as if it has been growing out for a few months."),

    # Hair Style
    "style_wavy": PromptSuggestion(emoji="🌊", text="Make Hair Wavy", prompt_for_enhancer="Change the hair texture to natural, soft waves."),
    "style_straight": PromptSuggestion(emoji="📏", text="Make Hair Sleek & Straight", prompt_for_enhancer="Change the hair texture to be perfectly straight and sleek."),
    "style_updo": PromptSuggestion(emoji="👱‍♀️", text="Create an Elegant Updo", prompt_for_enhancer="Restyle the hair into an elegant and simple updo, like a classic bun."),

    # Skin Details
    "add_freckles": PromptSuggestion(emoji="😊", text="Add Freckles", prompt_for_enhancer="Add a light, natural sprinkle of freckles across the nose and cheeks."),
    "remove_freckles": PromptSuggestion(emoji="🧼", text="Remove Freckles", prompt_for_enhancer="Completely remove all freckles, preserving skin texture."),
    "add_dimples": PromptSuggestion(emoji="😄", text="Add Dimples", prompt_for_enhancer="Add natural-looking dimples to the cheeks."),
    "remove_dimples": PromptSuggestion(emoji="✨", text="Remove Dimples", prompt_for_enhancer="Completely remove the dimples, preserving skin texture."),

    # Accessories
    "add_earrings": PromptSuggestion(emoji="💫", text="Add small heart earrings", prompt_for_enhancer="Add a pair of small, elegant rose gold heart earrings."),
    "remove_earrings": PromptSuggestion(emoji="👂", text="Remove Earrings", prompt_for_enhancer="Completely remove the earrings and reconstruct the earlobe."),
    "add_glasses": PromptSuggestion(emoji="👓", text="Add stylish glasses", prompt_for_enhancer="Add a pair of stylish eyeglasses with clear lenses."),
    "add_sunglasses": PromptSuggestion(emoji="🕶️", text="Add sunglasses", prompt_for_enhancer="Add a pair of classic, stylish sunglasses."),
    "remove_glasses": PromptSuggestion(emoji="😳", text="Remove Glasses", prompt_for_enhancer="Completely remove the eyeglasses."),
    "remove_sunglasses": PromptSuggestion(emoji="😎", text="Remove Sunglasses", prompt_for_enhancer="Completely remove the sunglasses and generate realistic eyes."),
    "add_necklace": PromptSuggestion(emoji="📿", text="Add a delicate necklace", prompt_for_enhancer="Add a single, delicate silver chain necklace."),
    "remove_necklace": PromptSuggestion(emoji="🧼", text="Remove Necklace", prompt_for_enhancer="Completely remove the necklace."),
    "add_cap": PromptSuggestion(emoji="🧢", text="Add a baseball cap", prompt_for_enhancer="Add a simple, stylish, forward-facing baseball cap."),
    "add_tiara": PromptSuggestion(emoji="👸", text="Add a small tiara", prompt_for_enhancer="Add a small, delicate, silver tiara with tiny sparkling diamonds."),
    "remove_headwear": PromptSuggestion(emoji="🚫", text="Remove Headwear", prompt_for_enhancer="Completely remove any headwear (hat, cap, etc.) and reconstruct the hair."),
}

# 2. UI STRUCTURE: A clean "blueprint" of the menu.
EDIT_MENU_STRUCTURE: dict[str, Any] = {
    "subcategories": {
        "face": {
            "title": "Improve Face", "emoji": "✨",
            "subcategories": {
                "eyes": {"title": "Change Eyes", "emoji": "👁️", "dynamic_key": "eyes"},
                "hair": {
                    "title": "Change Hair", "emoji": "💇",
                    "subcategories": {
                        "hair_tone": {"title": "Change Hair Tone", "emoji": "🎨", "suggestions": ["hair_lighter", "hair_darker"]},
                        "hair_length": {"title": "Change Hair Length", "emoji": "📏", "suggestions": ["hair_short", "hair_long"]},
                        "hair_style": {"title": "Change Hairstyle", "emoji": "💇‍♀️", "suggestions": ["style_wavy", "style_straight", "style_updo"]},
                    }
                },
                "skin_details": {"title": "Skin Details", "emoji": "✨", "dynamic_key": "skin_details"}
            }
        },
        "accessories": {
            "title": "Add/Remove Accessories", "emoji": "💍",
            "subcategories": {
                "eyewear": {
                    "title": "Eyewear", "emoji": "👓",
                    "dynamic_key": "eyewear"
                },
                "jewelry": {
                    "title": "Jewelry", "emoji": "💎",
                    "dynamic_key": "jewelry"
                },
                "headwear": {
                    "title": "Headwear", "emoji": "🎩",
                    "dynamic_key": "headwear"
                }
            }
        }
    }
}

# 3. UI STRUCTURE FOR GROUP PHOTOS
GROUP_PHOTO_EDIT_MENU_STRUCTURE: dict[str, Any] = {
    # This menu is intentionally simple for now. It will only show the
    # "Enter a Custom Prompt" button, as personalized suggestions for
    # group photos are not yet implemented.
    "subcategories": {}
}
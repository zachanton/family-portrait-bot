from aiogram_bot_template.data.settings import settings


def is_local_generation_enabled() -> bool:
    """Checks the config to see if any feature uses the 'local' client.

    Returns:
        True if any of the features or tiers use the local generation client; otherwise False.
    """
    # Check tiered generation features
    for tier in settings.child_generation.tiers.values():
        if tier.client.lower() == "local":
            return True

    for tier in settings.image_edit.tiers.values():
        if tier.client.lower() == "local":
            return True

    for tier in settings.upscale.tiers.values():
        if tier.client.lower() == "local":
            return True

    # Check non-generating features
    for feature in settings.ai_features.values():
        if feature.client.lower() == "local":
            return True

    return False

# aiogram_bot_template/services/clients/factory.py
from __future__ import annotations
import os
from typing import Any

from openai import AsyncOpenAI

from aiogram_bot_template.data.settings import settings
from aiogram_bot_template.data.constants import GenerationType

from .local_ai_client import LocalGenerationClient
from .mock_ai_client import MockAIClient
from .fal_async_client import FalAsyncClient
from .google_ai_client import GoogleAIClient

_PROVIDER_CONFIG = {
    "together": {"api_key_env": "TOGETHER_API_KEY", "base_url": str(settings.api_urls.together)},
    "nebius": {"api_key_env": "NEBIUS_API_KEY", "base_url": str(settings.api_urls.nebius)},
    "openai": {"api_key_env": "OPENAI_API_KEY", "base_url": str(settings.api_urls.openai)},
}

_CLIENT_CLASSES: dict[str, type[Any]] = {
    "mock": MockAIClient,
    "local": LocalGenerationClient,
    "fal": FalAsyncClient,
    "google": GoogleAIClient,
    **dict.fromkeys(_PROVIDER_CONFIG, AsyncOpenAI),
}


def _create_client_instance(client_name: str) -> Any:
    client_class = _CLIENT_CLASSES.get(client_name)
    if not client_class:
        raise ValueError(f"Unknown client type specified in config: '{client_name}'")

    if client_name in _PROVIDER_CONFIG:
        provider_config = _PROVIDER_CONFIG[client_name]
        api_key = os.getenv(provider_config["api_key_env"])
        if not api_key:
            raise RuntimeError(f"Missing API key for provider='{client_name}'. Set env var {provider_config['api_key_env']}.")
        return client_class(api_key=api_key, base_url=provider_config["base_url"])

    return client_class()

def get_ai_client_and_model(
    *,
    generation_type: GenerationType,
    quality: int,
) -> tuple[Any, str]:
    """
    Creates an AI client instance and returns it along with the model name,
    based on the generation type and quality tier from settings.
    """
    client_name, model_name = "", ""

    generation_config = getattr(settings, generation_type.value, None)

    if not generation_config or not hasattr(generation_config, "tiers"):
         raise ValueError(f"Configuration for generation type '{generation_type.value}' not found in settings.")

    tier_config = generation_config.tiers.get(quality)
    if tier_config:
        client_name, model_name = tier_config.client, tier_config.model

    if not client_name or not model_name:
        raise ValueError(f"Could not find a valid client/model configuration for the request: "
                         f"type='{generation_type}', quality='{quality}'.")

    client_instance = _create_client_instance(client_name.lower())
    return client_instance, model_name
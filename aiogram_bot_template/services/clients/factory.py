# aiogram_bot_template/services/clients/factory.py
from __future__ import annotations
import os
from typing import Any, overload

from openai import AsyncOpenAI

from aiogram_bot_template.data.settings import settings, AiFeatureConfig
from aiogram_bot_template.data.constants import GenerationType
from aiogram_bot_template.data.enums import AiFeature

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

    # This will now correctly handle the GoogleAIClient which doesn't need special args here
    return client_class()


def get_feature_config(feature: AiFeature) -> AiFeatureConfig:
    """
    Retrieves the complete configuration object for a given AI feature.
    """
    feature_config = settings.ai_features.get(feature.value)
    if not feature_config:
        raise ValueError(f"Configuration for AI feature '{feature.value}' not found.")
    return feature_config


@overload
def get_ai_client_and_model(*, feature: AiFeature) -> tuple[AsyncOpenAI | MockAIClient, str]: ...

@overload
def get_ai_client_and_model(*, generation_type: GenerationType, quality: int | None) -> tuple[AsyncOpenAI | MockAIClient | LocalGenerationClient | FalAIClient | GoogleAIClient, str]: ...


def get_ai_client_and_model(
    *,
    feature: AiFeature | None = None,
    generation_type: GenerationType | None = None,
    quality: int | None = None,
) -> tuple[Any, str]:
    client_name, model_name = "", ""

    if feature:
        feature_config = get_feature_config(feature)
        client_name, model_name = feature_config.client, feature_config.model

    elif generation_type and quality is not None:
        generation_config = getattr(settings, generation_type.value, None)

        if not generation_config or not hasattr(generation_config, "tiers"):
             raise ValueError(f"Configuration for generation type '{generation_type.value}' not found in settings.")

        tier_config = generation_config.tiers.get(quality)
        if tier_config:
            client_name, model_name = tier_config.client, tier_config.model

    if not client_name or not model_name:
        raise ValueError(f"Could not find a valid client/model configuration for the request: "
                         f"type='{generation_type}', quality='{quality}', feature='{feature}'.")

    client_instance = _create_client_instance(client_name.lower())
    return client_instance, model_name

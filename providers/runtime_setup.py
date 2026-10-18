"""Build the application provider registry from validated runtime configuration.

Cloud fallbacks are opt-in: by default JARVIS sends inference only to the
selected provider. Adding a cloud provider to JARVIS_FALLBACK_PROVIDERS means
prompts may be sent to that third-party service after a primary failure.
"""
from __future__ import annotations

import logging
import os
from typing import Any

from config.config import JarvisConfig
from config.providers import PROVIDER_CONFIG
from providers.health_monitor import HealthMonitor
from providers.provider_exceptions import ProviderConfigurationError
from providers.provider_factory import ProviderFactory
from providers.provider_registry import ProviderRegistry

logger = logging.getLogger(__name__)


def _provider_config(config: JarvisConfig, provider_id: str, *, primary: bool) -> dict[str, Any]:
    values: dict[str, Any] = dict(PROVIDER_CONFIG[provider_id])
    values["timeout_seconds"] = config.request_timeout
    values["max_retries"] = config.max_retries
    values["retry_backoff_seconds"] = config.retry_backoff_seconds

    if provider_id == "ollama":
        values["base_url"] = config.ollama_host
        values["default_embedding_model"] = config.embedding_model if primary else os.environ.get(
            "JARVIS_OLLAMA_EMBEDDING_MODEL", values["default_embedding_model"]
        )
        if primary:
            values["default_model"] = config.model
            values["models"] = config.get_role_models()
            values["models"]["general"] = config.model_general or config.model
            values["num_ctx"] = int(os.environ.get("JARVIS_NUM_CTX", values.get("num_ctx", 4096)))
            values["keep_alive"] = os.environ.get("JARVIS_KEEP_ALIVE", values.get("keep_alive", "5m"))
        else:
            roles = dict(values.get("models", {}))
            # Explicit fallback gets its own Ollama-native model map. Do not
            # accidentally send a cloud provider's JARVIS_MODEL to Ollama.
            if config.provider == "ollama":
                roles["general"] = config.model_general or config.model
            role_suffixes = {
                "general": "GENERAL",
                "reasoning": "REASONING",
                "coding": "CODING",
                "vision": "VISION",
                "fast": "FAST",
            }
            for role, suffix in role_suffixes.items():
                env_name = (
                    f"JARVIS_MODEL_{suffix}"
                    if config.provider == "ollama"
                    else f"JARVIS_OLLAMA_MODEL_{suffix}"
                )
                value = os.environ.get(env_name)
                if value:
                    roles[role] = value.strip()
            values["models"] = roles
            values["default_model"] = roles.get("general", values["default_model"])
            values["num_ctx"] = int(os.environ.get("JARVIS_OLLAMA_NUM_CTX", values.get("num_ctx", 4096)))
            values["keep_alive"] = os.environ.get("JARVIS_OLLAMA_KEEP_ALIVE", values.get("keep_alive", "5m"))
    else:
        model_env = f"JARVIS_{provider_id.upper()}_MODEL"
        values["default_model"] = (
            config.model if primary else os.environ.get(model_env, values["default_model"])
        )
        # Provider-native roles are kept separate from Ollama role tags.
        roles = dict(values.get("models", {"general": values["default_model"]}))
        roles["general"] = values["default_model"]
        for role in ("reasoning", "coding", "vision", "fast"):
            override = os.environ.get(f"JARVIS_{provider_id.upper()}_MODEL_{role.upper()}")
            if override:
                roles[role] = override.strip()
        values["models"] = roles
        if provider_id == "gemini":
            values["default_embedding_model"] = os.environ.get(
                "JARVIS_GEMINI_EMBEDDING_MODEL", values.get("default_embedding_model", "gemini-embedding-2")
            )
    return values


def build_provider_registry(
    config: JarvisConfig,
    health_monitor: HealthMonitor | None = None,
) -> tuple[ProviderRegistry, HealthMonitor]:
    """Create and initialize the configured primary and optional fallback providers.

    Primary provider errors are fatal and explicit. An optional fallback with
    missing credentials is omitted with a warning rather than breaking startup.
    Unknown providers are rejected by config loading before this function runs.
    """
    health = health_monitor or HealthMonitor()
    registry = ProviderRegistry(health)

    primary = ProviderFactory.create_provider(
        config.provider,
        config=_provider_config(config, config.provider, primary=True),
    )
    primary.initialize()
    registry.register(primary)

    for provider_id in config.fallback_providers:
        if provider_id == config.provider:
            raise ValueError("Primary provider cannot also be registered as a fallback")
        try:
            fallback = ProviderFactory.create_provider(
                provider_id,
                config=_provider_config(config, provider_id, primary=False),
            )
            fallback.initialize()
            registry.register(fallback)
        except ProviderConfigurationError as exc:
            # Missing cloud credentials disable this optional route; they do not
            # weaken the primary path or silently enable a different provider.
            logger.warning(
                "Skipping configured fallback provider %s (%s)",
                provider_id,
                type(exc).__name__,
            )
    return registry, health


def build_model_gateway(config: JarvisConfig):
    """Construct the application's single provider-routing gateway.

    Kept separate from main.py so CLI/Mission Control helpers can use precisely
    the same provider configuration and fallback policy as the desktop runtime.
    """
    from config.model_config import ModelRouterConfig
    from core.model_router import ModelRouter
    from providers.fallback_manager import FallbackManager
    from providers.selection_policy import WeightedScorePolicy

    registry, health = build_provider_registry(config)
    router_config = ModelRouterConfig(
        prefer_local=True,
        default_chat_provider=config.provider,
        default_reasoning_provider=config.reasoning_provider or config.provider,
        default_coding_provider=config.coding_provider or config.provider,
        default_vision_provider=config.vision_provider or config.provider,
        default_fast_provider=config.fast_provider or config.provider,
    )
    return ModelRouter(
        config=router_config,
        registry=registry,
        selection_policy=WeightedScorePolicy(health),
        fallback_manager=FallbackManager(),
        health_monitor=health,
    )

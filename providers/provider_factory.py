"""
Factory for instantiating AI providers.
"""

import logging
from typing import ClassVar

from providers.base_provider import BaseProvider
from providers.gemini_provider import GeminiProvider
from providers.ollama_provider import OllamaProvider
from providers.provider_exceptions import ProviderConfigurationError

logger = logging.getLogger(__name__)


class ProviderFactory:
    """Factory for creating provider instances."""

    _providers: ClassVar[dict[str, type[BaseProvider]]] = {
        "ollama": OllamaProvider,
        "gemini": GeminiProvider,
    }

    @classmethod
    def register_provider(cls, provider_id: str, provider_class: type[BaseProvider]) -> None:
        """Register a new provider class."""
        if provider_id in cls._providers:
            logger.warning("Overwriting existing provider registration for %s", provider_id)
        cls._providers[provider_id] = provider_class
        logger.info("Registered provider class for %s", provider_id)

    @classmethod
    def create_provider(cls, provider_id: str, **kwargs) -> BaseProvider:
        """Create and initialize a provider instance.
        
        Args:
            provider_id: The ID of the provider to instantiate.
            **kwargs: Additional configuration to pass to the provider constructor.
            
        Returns:
            An initialized instance of BaseProvider.
            
        Raises:
            ProviderConfigurationError: If the provider is unknown or fails to initialize.
        """
        provider_class = cls._providers.get(provider_id)
        if not provider_class:
            logger.error("Unknown provider requested: %s", provider_id)
            raise ProviderConfigurationError(f"Unknown provider ID: {provider_id}")
            
        try:
            logger.debug("Instantiating provider: %s", provider_id)
            provider = provider_class(**kwargs)
            return provider
        except Exception as e:
            logger.error("Failed to instantiate provider %s: %s", provider_id, e)
            raise ProviderConfigurationError(f"Failed to create provider {provider_id}: {e}") from e

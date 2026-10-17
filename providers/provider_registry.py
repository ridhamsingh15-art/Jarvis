"""
Provider registry for managing AI models.

Single source of truth for what providers exist and what their capabilities are.
"""

import logging
import threading

from providers.base_provider import BaseProvider
from providers.capabilities import Capability
from providers.health_monitor import HealthMonitor
from providers.provider_models import ProviderHealthStatus

logger = logging.getLogger(__name__)


class ProviderRegistry:
    """Thread-safe registry of AI providers."""

    def __init__(self, health_monitor: HealthMonitor) -> None:
        """Initialize the registry.
        
        Args:
            health_monitor: Monitor used to determine healthy providers.
        """
        self._lock = threading.RLock()
        self._providers: dict[str, BaseProvider] = {}
        self._health_monitor = health_monitor

    def register(self, provider: BaseProvider) -> None:
        """Register a new provider.
        
        Args:
            provider: The provider instance to register.
            
        Raises:
            ValueError: If a provider with the same ID is already registered.
            TypeError: If the object is not a BaseProvider.
        """
        if not isinstance(provider, BaseProvider):
            raise TypeError(f"Expected BaseProvider, got {type(provider)}")

        with self._lock:
            if provider.provider_id in self._providers:
                logger.error("Attempted to register duplicate provider_id: %s", provider.provider_id)
                raise ValueError(f"Provider with ID '{provider.provider_id}' is already registered.")
            
            self._providers[provider.provider_id] = provider
            logger.info(
                "Registered provider: %s (capabilities: %s)", 
                provider.provider_id, 
                ", ".join(c.name for c in provider.capabilities)
            )

    def unregister(self, provider_id: str) -> None:
        """Remove a provider from the registry.
        
        Args:
            provider_id: The ID of the provider to remove.
        """
        with self._lock:
            if provider_id in self._providers:
                del self._providers[provider_id]
                logger.info("Unregistered provider: %s", provider_id)

    def get_provider(self, provider_id: str) -> BaseProvider | None:
        """Get a specific provider by its ID.
        
        Args:
            provider_id: The ID to lookup.
            
        Returns:
            The provider instance, or None if not found.
        """
        with self._lock:
            return self._providers.get(provider_id)

    def list_providers(self) -> list[BaseProvider]:
        """List all registered providers.
        
        Returns:
            A list of all providers in registration order.
        """
        with self._lock:
            return list(self._providers.values())

    def list_by_capability(self, capability: Capability) -> list[BaseProvider]:
        """List all providers that support a specific capability.
        
        Args:
            capability: The required capability.
            
        Returns:
            A list of capable providers.
        """
        with self._lock:
            return [p for p in self._providers.values() if p.supports(capability)]

    def list_healthy_providers(self) -> list[BaseProvider]:
        """List all providers that are not UNAVAILABLE.
        
        Healthy and Degraded providers are included; Unavailable are excluded.
        
        Returns:
            A list of routable providers.
        """
        with self._lock:
            healthy = []
            for provider in self._providers.values():
                status = self._health_monitor.health(provider.provider_id)
                if status != ProviderHealthStatus.UNAVAILABLE:
                    healthy.append(provider)
            return healthy

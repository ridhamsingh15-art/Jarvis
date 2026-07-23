"""
Exception hierarchy for the provider integrations.
"""

from core.exceptions import JarvisError
from providers.provider_models import ProviderExecutionError


class ProviderConfigurationError(ProviderExecutionError):
    """Raised when a provider is misconfigured (e.g., missing API keys)."""
    pass


class ProviderConnectionError(ProviderExecutionError):
    """Raised when a provider cannot be reached."""
    pass


class ProviderAuthenticationError(ProviderConnectionError):
    """Raised when authentication with a provider fails."""
    pass


class ProviderTimeoutError(ProviderConnectionError):
    """Raised when a request to a provider times out."""
    pass


class ProviderRateLimitError(ProviderExecutionError):
    """Raised when a provider rate limit is exceeded."""
    pass


class ProviderAPIError(ProviderExecutionError):
    """Raised when a provider API returns an error response."""
    pass

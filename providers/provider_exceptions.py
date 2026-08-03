"""
Exception hierarchy for the provider integrations.
"""

from providers.provider_models import ProviderExecutionError


class ProviderConfigurationError(ProviderExecutionError):
    """Raised when a provider is misconfigured (e.g., missing API keys)."""


class ProviderConnectionError(ProviderExecutionError):
    """Raised when a provider cannot be reached."""


class ProviderAuthenticationError(ProviderConnectionError):
    """Raised when authentication with a provider fails."""


class ProviderTimeoutError(ProviderConnectionError):
    """Raised when a request to a provider times out."""


class ProviderRateLimitError(ProviderExecutionError):
    """Raised when a provider rate limit is exceeded."""


class ProviderAPIError(ProviderExecutionError):
    """Raised when a provider API returns an error response."""

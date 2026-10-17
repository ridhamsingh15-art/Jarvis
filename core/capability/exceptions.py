"""
Exceptions for the Capability Router subsystem.
"""

from core.exceptions import JarvisError


class CapabilityError(JarvisError):
    """Base exception for capability routing errors."""


class RoutingError(CapabilityError):
    """Raised when the router fails to generate a valid capability plan."""


class ModelSelectionError(CapabilityError):
    """Raised when a suitable model cannot be selected for the requested capabilities."""


class CapabilityNotFoundError(CapabilityError):
    """Raised when a requested capability is not registered."""

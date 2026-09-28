"""
Registry for JARVIS capabilities.
"""

from collections.abc import Iterable

from core.capability.exceptions import CapabilityNotFoundError
from core.capability.models import Capability


class CapabilityRegistry:
    """Central registry for all system capabilities (subsystems, tools, agents)."""

    def __init__(self) -> None:
        self._capabilities: dict[str, Capability] = {}

    def register(self, capability: Capability) -> None:
        """Register a new capability."""
        self._capabilities[capability.name] = capability

    def get(self, name: str) -> Capability:
        """Retrieve a registered capability by name.
        
        Args:
            name: The name of the capability.
            
        Returns:
            The capability metadata.
            
        Raises:
            CapabilityNotFoundError: If the capability is not registered.
        """
        if name not in self._capabilities:
            raise CapabilityNotFoundError(f"Capability '{name}' is not registered.")
        return self._capabilities[name]

    def list_all(self) -> Iterable[Capability]:
        """Iterate over all registered capabilities."""
        return self._capabilities.values()

    def has(self, name: str) -> bool:
        """Check if a capability is registered."""
        return name in self._capabilities

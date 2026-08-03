from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .enums import ServiceLifetime


@dataclass
class ServiceRegistration:
    """
    Metadata for a registered service in the DI Container.
    """
    interface: type
    lifetime: ServiceLifetime
    implementation_type: type | None = None
    factory: Callable[..., Any] | None = None
    instance: Any | None = None
    
    # Internal cache for Singleton/Scoped resolution
    _instance_cache: Any | None = None

    def __post_init__(self):
        pass

    def get_dependencies(self) -> dict:
        """
        Uses Python's inspect module to determine dependencies of the target.
        Implemented via the resolver later.
        """
        return {}

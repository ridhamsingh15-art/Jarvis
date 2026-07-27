from dataclasses import dataclass
from typing import Any, Callable, Optional, Type
from .enums import ServiceLifetime

@dataclass
class ServiceRegistration:
    """
    Metadata for a registered service in the DI Container.
    """
    interface: Type
    lifetime: ServiceLifetime
    implementation_type: Optional[Type] = None
    factory: Optional[Callable[..., Any]] = None
    instance: Optional[Any] = None
    
    # Internal cache for Singleton/Scoped resolution
    _instance_cache: Optional[Any] = None

    def get_dependencies(self) -> dict:
        """
        Uses Python's inspect module to determine dependencies of the target.
        Implemented via the resolver later.
        """
        pass

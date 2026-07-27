"""
JARVIS AIOS Dependency Injection Subsystem

Provides a strict, validate-able, and sealed IoC container to manage
service lifetimes across the runtime.
"""

from .enums import ServiceLifetime
from .exceptions import DependencyResolutionError, CircularDependencyError, ContainerSealedError
from .container import Container, ServiceScope

__all__ = [
    "ServiceLifetime",
    "DependencyResolutionError", 
    "CircularDependencyError", 
    "ContainerSealedError",
    "Container", 
    "ServiceScope"
]

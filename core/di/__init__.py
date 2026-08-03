"""
JARVIS AIOS Dependency Injection Subsystem

Provides a strict, validate-able, and sealed IoC container to manage
service lifetimes across the runtime.
"""

from .container import Container, ServiceScope
from .enums import ServiceLifetime
from .exceptions import (
    CircularDependencyError,
    ContainerSealedError,
    DependencyResolutionError,
)

__all__ = [
    "CircularDependencyError",
    "Container",
    "ContainerSealedError",
    "DependencyResolutionError",
    "ServiceLifetime",
    "ServiceScope"
]

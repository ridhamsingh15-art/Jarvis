"""
JARVIS AIOS Core Models

The canonical, immutable domain models mapped across the entire operating system.
No raw dictionaries should cross subsystem boundaries.
"""

from .base import JarvisModel
from .domain import (
    Artifact,
    Command,
    Context,
    Event,
    ExecutionResult,
    Message,
    Resource,
    Task,
)
from .enums import Capability, ExecutionState, Permission
from .exceptions import ModelValidationError
from .primitives import Identifier, Metadata, Timestamp, Version

__all__ = [
    "Artifact",
    "Capability",
    "Command",
    "Context",
    "Event",
    "ExecutionResult",
    "ExecutionState",
    "Identifier",
    "JarvisModel",
    "Message",
    "Metadata",
    "ModelValidationError",
    "Permission",
    "Resource",
    "Task",
    "Timestamp",
    "Version"
]

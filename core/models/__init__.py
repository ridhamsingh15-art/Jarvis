"""
JARVIS AIOS Core Models

The canonical, immutable domain models mapped across the entire operating system.
No raw dictionaries should cross subsystem boundaries.
"""

from .exceptions import ModelValidationError
from .enums import ExecutionState, Capability, Permission
from .base import JarvisModel
from .primitives import Identifier, Timestamp, Version, Metadata
from .domain import (
    ExecutionResult, Artifact, Resource, Context,
    Event, Message, Command, Task
)

__all__ = [
    "ModelValidationError",
    "ExecutionState", "Capability", "Permission",
    "JarvisModel",
    "Identifier", "Timestamp", "Version", "Metadata",
    "ExecutionResult", "Artifact", "Resource", "Context",
    "Event", "Message", "Command", "Task"
]

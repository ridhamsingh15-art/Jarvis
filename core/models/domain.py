from dataclasses import dataclass, field
from typing import Any

from .base import JarvisModel
from .enums import Capability, ExecutionState, Permission
from .primitives import Identifier, Metadata, Timestamp, Version


@dataclass(frozen=True, slots=True)
class ExecutionResult(JarvisModel):
    """The standardized output of any execution block."""
    success: bool
    output: dict[str, Any] = field(default_factory=dict)
    error_message: str | None = None
    execution_time_ms: int = 0

@dataclass(frozen=True, slots=True)
class Artifact(JarvisModel):
    """Represents a generated output file or object."""
    id: Identifier
    name: str
    path: str
    mime_type: str = "application/octet-stream"
    metadata: Metadata = field(default_factory=Metadata)

@dataclass(frozen=True, slots=True)
class Resource(JarvisModel):
    """A bounded system resource (file, memory buffer, socket)."""
    id: Identifier
    type: str
    uri: str
    capabilities: list[Capability] = field(default_factory=list)

@dataclass(frozen=True, slots=True)
class Context(JarvisModel):
    """Execution context injected into operations."""
    correlation_id: Identifier
    session_id: Identifier
    permissions: list[Permission] = field(default_factory=list)
    metadata: Metadata = field(default_factory=Metadata)

@dataclass(frozen=True, slots=True)
class Event(JarvisModel):
    """System-wide pub/sub event."""
    id: Identifier = field(default_factory=Identifier)
    timestamp: Timestamp = field(default_factory=Timestamp)
    topic: str = "system.default"
    payload: dict[str, Any] = field(default_factory=dict)
    source: str = "unknown"

@dataclass(frozen=True, slots=True)
class Message(JarvisModel):
    """Agent-to-Agent or Agent-to-User communication."""
    id: Identifier = field(default_factory=Identifier)
    timestamp: Timestamp = field(default_factory=Timestamp)
    sender: str = "system"
    receiver: str = "user"
    content: str = ""
    metadata: Metadata = field(default_factory=Metadata)

@dataclass(frozen=True, slots=True)
class Command(JarvisModel):
    """A strict imperative action bound for a provider or tool."""
    id: Identifier = field(default_factory=Identifier)
    action: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)
    context: Context | None = None

@dataclass(frozen=True, slots=True)
class Task(JarvisModel):
    """A complex execution unit managed by the Planner."""
    id: Identifier = field(default_factory=Identifier)
    name: str = "Unnamed Task"
    description: str = ""
    state: ExecutionState = ExecutionState.PENDING
    commands: list[Command] = field(default_factory=list)
    result: ExecutionResult | None = None
    created_at: Timestamp = field(default_factory=Timestamp)
    updated_at: Timestamp = field(default_factory=Timestamp)
    version: Version = field(default_factory=Version)
    metadata: Metadata = field(default_factory=Metadata)

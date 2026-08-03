from dataclasses import dataclass, field
from typing import Any

from core.models import Identifier, JarvisModel, Timestamp

from .enums import MemoryType


@dataclass(frozen=True, slots=True)
class MemoryItem(JarvisModel):
    """Base class for all immutable memory models."""
    id: Identifier = field(default_factory=Identifier)
    memory_type: MemoryType = MemoryType.WORKING
    created_at: Timestamp = field(default_factory=Timestamp)

@dataclass(frozen=True, slots=True)
class WorkingMemoryItem(MemoryItem):
    """Temporary scratchpad memory with optional TTL."""
    key: str = ""
    value: Any = None
    ttl_seconds: float | None = None
    expires_at: float | None = None

@dataclass(frozen=True, slots=True)
class EpisodicEvent(MemoryItem):
    """Immutable chronological log of a system or user event."""
    event_type: str = "UNKNOWN"
    payload: dict[str, Any] = field(default_factory=dict)
    source: str = "system"

@dataclass(frozen=True, slots=True)
class SemanticFact(MemoryItem):
    """Immutable knowledge fact representing an entity relationship."""
    entity: str = ""
    relationship: str = ""
    target: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

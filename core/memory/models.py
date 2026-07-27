from dataclasses import dataclass, field
from typing import Dict, Any, Optional
import time

from core.models import JarvisModel, Identifier, Timestamp
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
    ttl_seconds: Optional[float] = None
    expires_at: Optional[float] = None

@dataclass(frozen=True, slots=True)
class EpisodicEvent(MemoryItem):
    """Immutable chronological log of a system or user event."""
    event_type: str = "UNKNOWN"
    payload: Dict[str, Any] = field(default_factory=dict)
    source: str = "system"

@dataclass(frozen=True, slots=True)
class SemanticFact(MemoryItem):
    """Immutable knowledge fact representing an entity relationship."""
    entity: str = ""
    relationship: str = ""
    target: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

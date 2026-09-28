import builtins
from dataclasses import dataclass, field
from typing import Any

from core.models import JarvisModel
from core.models.primitives import Identifier, Timestamp

from .enums import AgentRole, CollaborationState, TaskState, VoteType


@dataclass(frozen=True, slots=True)
class AgentCapability(JarvisModel):
    """Immutable capability representation."""
    name: str
    description: str


@dataclass(frozen=True, slots=True)
class AgentProfile(JarvisModel):
    """Immutable identity containing role and capabilities."""
    id: Identifier
    role: AgentRole
    capabilities: builtins.list[AgentCapability] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class AgentTask(JarvisModel):
    """Context for an assignment."""
    id: Identifier
    intent: str
    payload: dict[str, Any] = field(default_factory=dict)
    timeout: int = 300
    max_retries: int = 3
    timestamp: Timestamp = field(default_factory=Timestamp)


@dataclass(frozen=True, slots=True)
class AgentResult(JarvisModel):
    """Execution output from an agent task."""
    task_id: Identifier
    status: TaskState
    payload: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)
    timestamp: Timestamp = field(default_factory=Timestamp)


@dataclass(frozen=True, slots=True)
class CollaborationSession(JarvisModel):
    """Context tracking active parallel jobs."""
    id: Identifier
    state: CollaborationState
    participants: builtins.list[Identifier] = field(default_factory=list)
    timestamp: Timestamp = field(default_factory=Timestamp)


@dataclass(frozen=True, slots=True)
class Vote(JarvisModel):
    """Struct mapping an agent to a decision and weight."""
    agent_id: Identifier
    decision: VoteType
    weight: float = 1.0


@dataclass(frozen=True, slots=True)
class SharedContext(JarvisModel):
    """Immutable read-only boundary for passing contextual states."""
    session_id: Identifier
    read_only_data: dict[str, Any] = field(default_factory=dict)
    timestamp: Timestamp = field(default_factory=Timestamp)

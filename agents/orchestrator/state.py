from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from core.models import JarvisModel


class NodeState(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

@dataclass(frozen=True)
class WorkflowNode(JarvisModel):
    id: str
    action: str
    payload: dict[str, Any] = field(default_factory=dict)
    retries: int = 3

@dataclass
class WorkflowState:
    id: str
    nodes: dict[str, WorkflowNode] = field(default_factory=dict)
    dependencies: dict[str, set[str]] = field(default_factory=dict)
    node_states: dict[str, NodeState] = field(default_factory=dict)
    results: dict[str, Any] = field(default_factory=dict)

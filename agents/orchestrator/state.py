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

    def validate(self) -> None:
        if (
            not isinstance(self.retries, int)
            or isinstance(self.retries, bool)
            or self.retries < 1
        ):
            raise ValueError("retries must be an integer greater than or equal to 1")

@dataclass
class WorkflowState:
    id: str
    nodes: dict[str, WorkflowNode] = field(default_factory=dict)
    dependencies: dict[str, set[str]] = field(default_factory=dict)
    node_states: dict[str, NodeState] = field(default_factory=dict)
    results: dict[str, Any] = field(default_factory=dict)

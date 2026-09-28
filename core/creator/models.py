from dataclasses import dataclass, field
from enum import StrEnum
from typing import List, Dict, Optional, Set

from core.models.primitives import Identifier

class ProductionState(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"

@dataclass(frozen=True)
class CreatorObjective:
    """Represents the parsed high-level user goal."""
    id: Identifier
    raw_prompt: str
    target_format: str  # e.g., "video", "short", "documentary"
    topic: str
    required_capabilities: List[str] = field(default_factory=list)

@dataclass
class WorkflowNode:
    """A single stage in the Creator's production pipeline."""
    id: str  # e.g., "research", "script", "storyboard"
    capability: str # The required capability/intent (e.g., "web_search", "script_writing")
    description: str
    dependencies: Set[str] = field(default_factory=set)
    state: ProductionState = ProductionState.PENDING
    result_payload: Dict[str, str] = field(default_factory=dict)
    error_message: Optional[str] = None

@dataclass
class DependencyGraph:
    """A directed acyclic graph representing the order of production stages."""
    nodes: Dict[str, WorkflowNode] = field(default_factory=dict)

    def add_node(self, node: WorkflowNode) -> None:
        self.nodes[node.id] = node

    def add_dependency(self, node_id: str, depends_on_id: str) -> None:
        if node_id in self.nodes and depends_on_id in self.nodes:
            self.nodes[node_id].dependencies.add(depends_on_id)

@dataclass
class ProgressReport:
    """A snapshot of the current overall production progress."""
    mission_id: str
    overall_progress_percent: float
    completed_stages: List[str]
    running_stage: Optional[str]
    failed_stages: List[str]
    skipped_stages: List[str]

import uuid

from .dependency_graph import DependencyGraph
from .state import WorkflowNode, WorkflowState


class WorkflowBuilder:
    def __init__(self, workflow_id: str):
        self.state = WorkflowState(id=workflow_id)
        self.graph = DependencyGraph(self.state)

    def add_task(self, action: str, deps: list[str] | None = None) -> str:
        nid = f"task_{uuid.uuid4().hex[:8]}"
        self.graph.add_node(WorkflowNode(id=nid, action=action), deps)
        return nid

    def build(self) -> DependencyGraph:
        self.graph.detect_cycles()
        return self.graph

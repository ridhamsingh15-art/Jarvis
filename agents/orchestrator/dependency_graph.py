from .state import NodeState, WorkflowNode, WorkflowState


class CycleError(Exception):
    pass

class DependencyGraph:
    def __init__(self, state: WorkflowState):
        self.state = state

    def add_node(self, node: WorkflowNode, deps: list[str] | None = None) -> None:
        self.state.nodes[node.id] = node
        self.state.dependencies[node.id] = set(deps) if deps else set()
        self.state.node_states[node.id] = NodeState.PENDING

    def get_ready_nodes(self) -> list[WorkflowNode]:
        ready = []
        for nid, deps in self.state.dependencies.items():
            if self.state.node_states[nid] != NodeState.PENDING:
                continue
            # Check if all deps are completed
            if all(self.state.node_states.get(d) == NodeState.COMPLETED for d in deps):
                ready.append(self.state.nodes[nid])
        return ready

    def detect_cycles(self) -> None:
        visited = set()
        path = set()

        def visit(nid: str) -> None:
            if nid in path:
                raise CycleError(f"Cycle detected at node {nid}")
            if nid in visited:
                return
            path.add(nid)
            for d in self.state.dependencies.get(nid, set()):
                visit(d)
            path.remove(nid)
            visited.add(nid)

        for node_id in self.state.nodes:
            visit(node_id)

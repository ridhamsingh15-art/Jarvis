from .state import NodeState, WorkflowState


class WorkflowRecovery:
    def __init__(self) -> None:
        self._checkpoints: dict[str, dict] = {}

    def checkpoint(self, state: WorkflowState) -> None:
        # Simple mock serialization
        self._checkpoints[state.id] = {
            "states": {k: v.value for k, v in state.node_states.items()},
            "results": state.results.copy()
        }

    def load(self, state: WorkflowState) -> None:
        cp = self._checkpoints.get(state.id)
        if cp:
            for k, v in cp["states"].items():
                state.node_states[k] = NodeState(v)
            state.results.update(cp["results"])

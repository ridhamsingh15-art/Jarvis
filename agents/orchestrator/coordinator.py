from .state import WorkflowState


class WorkflowCoordinator:
    def merge_outputs(self, state: WorkflowState) -> dict[str, str]:
        return {k: str(v) for k, v in state.results.items()}

from .project import ProjectPhase, ProjectState


class RecoveryController:
    def restore(self, state: ProjectState) -> None:
        state.errors.clear()
        state.phase = ProjectPhase.IMPLEMENTATION

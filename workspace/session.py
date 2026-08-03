from .workspace import WorkspaceState


class SessionContext:
    def build_context(self) -> WorkspaceState:
        state = WorkspaceState()
        state.active_project = "JARVIS AIOS"
        state.active_repository = "git@github.com:jarvis/jarvis.git"
        return state

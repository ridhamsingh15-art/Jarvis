from .project import ProjectState


class ReleaseManager:
    def release(self, state: ProjectState) -> str:
        return "v1.0.0"

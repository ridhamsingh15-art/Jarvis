from .project import ProjectState


class DeploymentEngine:
    def deploy(self, state: ProjectState, version: str) -> bool:
        return True

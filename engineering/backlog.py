from .project import ProjectState


class RequirementsParser:
    def parse(self, state: ProjectState) -> list[str]:
        # Transforms abstract objective into stories
        return [f"Implement core logic for {state.objective}", "Write integration tests"]

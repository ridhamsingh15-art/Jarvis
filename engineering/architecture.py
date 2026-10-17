from .project import ProjectState


class ArchitectureDesigner:
    def design(self, state: ProjectState) -> str:
        # Outlines dependencies
        return f"Architecture for {state.objective}: MVC structure"

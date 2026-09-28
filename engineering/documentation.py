from .project import ProjectState


class DocumentationGenerator:
    def generate(self, state: ProjectState) -> dict[str, str]:
        return {
            "README.md": f"# {state.objective}\nGenerated documentation.",
            "API.md": "## API Docs\nEndpoints listed here."
        }

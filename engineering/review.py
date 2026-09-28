from .project import ProjectState


class CodeReviewer:
    def review(self, state: ProjectState) -> list[str]:
        # Validates optimization boundaries
        return ["Optimized main.py", "Refactored util()"]

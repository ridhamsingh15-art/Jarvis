"""
Registry for mapping JARVIS-friendly workflow names to n8n workflows.
"""

from .exceptions import N8nWorkflowNotFoundError
from .models import N8nWorkflow


class N8nWorkflowRegistry:
    """Stores known workflows that JARVIS can orchestrate."""

    def __init__(self) -> None:
        self._workflows: dict[str, N8nWorkflow] = {}

    def register(self, workflow: N8nWorkflow) -> None:
        """Registers a new workflow by its friendly name."""
        self._workflows[workflow.name.lower()] = workflow

    def get(self, name: str) -> N8nWorkflow:
        """Retrieves a workflow by its friendly name."""
        workflow = self._workflows.get(name.lower())
        if not workflow:
            raise N8nWorkflowNotFoundError(f"Workflow '{name}' is not registered.")
        return workflow

    def list_all(self) -> list[N8nWorkflow]:
        """Returns all registered workflows."""
        return list(self._workflows.values())

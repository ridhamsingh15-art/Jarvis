"""
Public Capability Facade for n8n.
"""

from typing import Any

from core.capability.models import Capability, CapabilityType

from .installer import N8nInstaller
from .workflow_registry import N8nWorkflowRegistry
from .workflow_runner import N8nWorkflowRunner


class N8nCapabilityManager:
    """Provides high-level automation capabilities using n8n."""

    def __init__(
        self,
        installer: N8nInstaller,
        registry: N8nWorkflowRegistry,
        runner: N8nWorkflowRunner
    ) -> None:
        self._installer = installer
        self._registry = registry
        self._runner = runner

    def initialize(self) -> None:
        """Runs the dependency management logic."""
        if not self._installer.check_health():
            self._installer.request_installation()

    def get_capability_metadata(self) -> Capability:
        """Returns the Capability model for router registration."""
        return Capability(
            name="automation",
            description="Executes external workflows, scripts, social media uploads, data syncs, and custom automations.",
            type=CapabilityType.INTEGRATION
        )

    def execute_workflow_by_name(self, workflow_name: str, payload: dict[str, Any]) -> str:
        """Triggers a registered workflow and returns the Mission ID."""
        workflow = self._registry.get(workflow_name)
        return self._runner.execute_async(workflow, payload)
        
    def list_workflows(self) -> list[str]:
        """Returns the names of all registered workflows."""
        return [w.name for w in self._registry.list_all()]

"""
World Model Manager — the façade for the entire World Model subsystem.

Usage::

    world = WorldManager.create_default(plugins_dir="plugins/")
    world.register_workspace("C:/Users/ridha/Projects/Jarvis", "Jarvis")

    # Before planning
    state = world.snapshot()
    prompt_block = state.format_for_prompt()

    # Context integration
    ctx.inject_system_note(prompt_block)
"""
from __future__ import annotations

import logging
from typing import Optional

from .browser_monitor import BrowserMonitor
from .exceptions import WorkspaceAlreadyRegisteredError
from .git_monitor import GitMonitor
from .models import ActiveMissionRef, RegisteredWorkspace, WorldState
from .observers import WorldObservers
from .process_monitor import ProcessMonitor
from .snapshot import WorldSnapshot
from .window_monitor import WindowMonitor
from .workspace import WorkspaceRegistry

logger = logging.getLogger(__name__)


class WorldManager:
    """
    Central façade for the World Model subsystem.

    Manages workspace registration, observer lifecycle, and snapshot generation.
    Integrates with the Context Orchestrator and Executive Brain via
    ``snapshot().format_for_prompt()``.
    """

    def __init__(
        self,
        workspace_registry: WorkspaceRegistry,
        observers: WorldObservers,
        browser_monitor: BrowserMonitor,
    ) -> None:
        self._workspace_registry = workspace_registry
        self._observers = observers
        self._browser_monitor = browser_monitor
        self._snapshot_engine = WorldSnapshot(workspace_registry, observers)

    @classmethod
    def create_default(cls) -> "WorldManager":
        """Factory that wires up default concrete observers."""
        registry = WorkspaceRegistry()
        observers = WorldObservers(
            git_monitor=GitMonitor(),
            process_monitor=ProcessMonitor(),
            window_monitor=WindowMonitor(),
        )
        browser = BrowserMonitor()
        return cls(registry, observers, browser)

    # ------------------------------------------------------------------
    # Workspace Management
    # ------------------------------------------------------------------

    def register_workspace(self, path: str, name: Optional[str] = None) -> RegisteredWorkspace:
        """Register a trusted workspace folder."""
        return self._workspace_registry.register(path, name)

    def remove_workspace(self, workspace_id: str) -> None:
        """Remove a registered workspace."""
        self._workspace_registry.remove(workspace_id)

    def list_workspaces(self) -> list[RegisteredWorkspace]:
        """List all registered trusted workspaces."""
        return self._workspace_registry.list()

    # ------------------------------------------------------------------
    # Snapshot
    # ------------------------------------------------------------------

    def snapshot(
        self,
        active_missions: Optional[list[ActiveMissionRef]] = None,
    ) -> WorldState:
        """
        Capture a fresh immutable WorldState.

        Typically called by the Executive Brain's ``plan()`` method, or by the
        Context Orchestrator when building the planning prompt.
        """
        state = self._snapshot_engine.capture(active_missions=active_missions)
        logger.debug(
            f"WorldState captured: {len(state.registered_workspaces)} workspaces, "
            f"{len(state.git_statuses)} git repos, "
            f"{len(state.running_processes)} processes"
        )
        return state

    def snapshot_for_prompt(
        self,
        active_missions: Optional[list[ActiveMissionRef]] = None,
    ) -> str:
        """
        Convenience method: capture a snapshot and format it as a prompt block.
        """
        return self.snapshot(active_missions).format_for_prompt()

    # ------------------------------------------------------------------
    # Browser (plugin-push API)
    # ------------------------------------------------------------------

    def push_browser_tabs(self, tabs: list[dict]) -> None:
        """
        Accept browser tab data pushed from an approved browser plugin.
        Never called directly by JARVIS internals.
        """
        self._browser_monitor.push_tabs(tabs)

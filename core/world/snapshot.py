"""
World Snapshot.

Assembles a single immutable WorldState from all registered observers,
with relevance filtering so only actionable data is injected into prompts.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from .exceptions import SnapshotError
from .models import ActiveMissionRef, WorldState
from .observers import WorldObservers
from .workspace import WorkspaceRegistry

logger = logging.getLogger(__name__)


class WorldSnapshot:
    """
    Generates immutable WorldState snapshots on demand.
    Each call to ``capture()`` is a fresh observation.
    """

    def __init__(
        self,
        workspace_registry: WorkspaceRegistry,
        observers: WorldObservers,
    ) -> None:
        self._workspace_registry = workspace_registry
        self._observers = observers

    def capture(
        self,
        active_missions: Optional[list[ActiveMissionRef]] = None,
    ) -> WorldState:
        """
        Perform a fresh observation of all registered subsystems and return
        an immutable WorldState snapshot.
        """
        try:
            workspaces = self._workspace_registry.list()

            # Determine active workspace heuristically:
            # prioritise any workspace whose path appears in the focused window title
            focused = self._observers.collect_focused_window()
            active_workspace = None
            if focused and focused.workspace_path:
                active_workspace = self._workspace_registry.find_by_path(
                    focused.workspace_path
                )
            if active_workspace is None and workspaces:
                active_workspace = workspaces[0]  # fallback: first registered

            return WorldState(
                captured_at=datetime.now(timezone.utc).isoformat(),
                registered_workspaces=workspaces,
                active_workspace=active_workspace,
                git_statuses=self._observers.collect_git(workspaces),
                running_processes=self._observers.collect_processes(),
                focused_window=focused,
                recent_windows=self._observers.collect_recent_windows(),
                active_missions=active_missions or [],
            )

        except Exception as e:
            raise SnapshotError(f"Could not generate WorldState: {e}") from e

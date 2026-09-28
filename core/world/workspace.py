"""
Workspace Registry.

Manages user-registered workspace folders. Only registered workspaces
are ever observed — JARVIS never indexes arbitrary user files.
"""
from __future__ import annotations

import logging
import os
import threading
import uuid
from datetime import datetime, timezone
from typing import Optional

from .exceptions import WorkspaceAlreadyRegisteredError, WorkspaceNotFoundError
from .models import RegisteredWorkspace

logger = logging.getLogger(__name__)

# Heuristics to auto-detect the primary language in a workspace
_LANG_HINTS: list[tuple[str, str]] = [
    ("requirements.txt",   "Python"),
    ("pyproject.toml",     "Python"),
    ("package.json",       "JavaScript/TypeScript"),
    ("Cargo.toml",         "Rust"),
    ("go.mod",             "Go"),
    ("pom.xml",            "Java"),
    ("build.gradle",       "Java/Kotlin"),
    ("*.sln",              "C#"),
    ("CMakeLists.txt",     "C/C++"),
]


def _detect_language(path: str) -> Optional[str]:
    try:
        entries = set(os.listdir(path))
        for marker, lang in _LANG_HINTS:
            if marker.startswith("*"):
                ext = marker[1:]
                if any(f.endswith(ext) for f in entries):
                    return lang
            elif marker in entries:
                return lang
    except OSError:
        pass
    return None


class WorkspaceRegistry:
    """Thread-safe registry of user-trusted workspace folders."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._workspaces: dict[str, RegisteredWorkspace] = {}  # id -> workspace

    def register(self, path: str, name: Optional[str] = None) -> RegisteredWorkspace:
        """
        Register a new trusted workspace. The path must exist.
        Raises WorkspaceAlreadyRegisteredError if the path is already tracked.
        """
        abs_path = os.path.abspath(path)
        if not os.path.isdir(abs_path):
            raise WorkspaceNotFoundError(f"Path does not exist: {abs_path}")

        with self._lock:
            for ws in self._workspaces.values():
                if ws.path == abs_path:
                    raise WorkspaceAlreadyRegisteredError(
                        f"Workspace already registered: {abs_path}"
                    )
            ws_id = f"ws_{uuid.uuid4().hex[:8]}"
            language = _detect_language(abs_path)
            workspace = RegisteredWorkspace(
                id=ws_id,
                path=abs_path,
                name=name or os.path.basename(abs_path),
                language=language,
                registered_at=datetime.now(timezone.utc).isoformat(),
            )
            self._workspaces[ws_id] = workspace
            logger.info(f"Workspace registered: {workspace.name} ({abs_path})")
            return workspace

    def remove(self, workspace_id: str) -> None:
        with self._lock:
            if workspace_id not in self._workspaces:
                raise WorkspaceNotFoundError(f"Workspace not found: {workspace_id}")
            removed = self._workspaces.pop(workspace_id)
            logger.info(f"Workspace removed: {removed.name}")

    def get(self, workspace_id: str) -> Optional[RegisteredWorkspace]:
        with self._lock:
            return self._workspaces.get(workspace_id)

    def find_by_path(self, path: str) -> Optional[RegisteredWorkspace]:
        abs_path = os.path.abspath(path)
        with self._lock:
            for ws in self._workspaces.values():
                if ws.path == abs_path or abs_path.startswith(ws.path):
                    return ws
        return None

    def list(self) -> list[RegisteredWorkspace]:
        with self._lock:
            return list(self._workspaces.values())

"""
Git Monitor.

Reads live git repository state for each registered workspace.
Uses subprocess calls to the local git binary — no third-party library needed.
"""
from __future__ import annotations

import logging
import subprocess
from typing import Optional

from .exceptions import ObserverError
from .models import GitRepoStatus, GitStatus, RegisteredWorkspace

logger = logging.getLogger(__name__)

_MAX_COMMITS = 3
_GIT_TIMEOUT = 3   # seconds per subprocess call


def _run_git(args: list[str], cwd: str) -> Optional[str]:
    """Run a git subcommand and return stdout, or None on error."""
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return None


class GitMonitor:
    """
    Detects and reads the git state of registered workspaces.
    Safe to call repeatedly — each call is a fresh read (no caching).
    """

    def observe(self, workspace: RegisteredWorkspace) -> Optional[GitStatus]:
        """
        Return a GitStatus for the workspace, or None if it is not a git repo.
        """
        path = workspace.path

        # Is this a git repo?
        root = _run_git(["rev-parse", "--show-toplevel"], path)
        if root is None:
            return None

        branch = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], path) or "unknown"

        # Dirty check
        status_output = _run_git(["status", "--short"], path) or ""
        lines = [l for l in status_output.splitlines() if l.strip()]
        is_dirty = len(lines) > 0

        modified: list[str] = []
        staged: list[str] = []
        for line in lines:
            if len(line) >= 2:
                xy = line[:2]
                fname = line[3:].strip()
                if xy[0] in ("M", "A", "D", "R"):
                    staged.append(fname)
                if xy[1] in ("M", "D", "?"):
                    modified.append(fname)

        # Recent commits
        log = _run_git(
            ["log", f"--max-count={_MAX_COMMITS}", "--oneline"],
            path
        ) or ""
        recent_commits = [c for c in log.splitlines() if c.strip()]

        return GitStatus(
            workspace_id=workspace.id,
            repo_path=root,
            current_branch=branch,
            is_dirty=is_dirty,
            status=GitRepoStatus.DIRTY if is_dirty else GitRepoStatus.CLEAN,
            modified_files=modified,
            staged_files=staged,
            recent_commits=recent_commits,
        )

    def observe_all(self, workspaces: list[RegisteredWorkspace]) -> list[GitStatus]:
        results: list[GitStatus] = []
        for ws in workspaces:
            try:
                status = self.observe(ws)
                if status:
                    results.append(status)
            except Exception as e:  # noqa: BLE001
                logger.warning(f"Git observer failed for {ws.path}: {e}")
        return results

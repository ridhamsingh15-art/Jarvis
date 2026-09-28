"""
Git Manager.

Manages version control operations for the software engineering workflow.
Strictly sandboxed to local operations (branch, commit, checkout).
Never pushes remotely to prevent destructive actions without user consent.
"""
import logging
import subprocess
import os
from typing import Optional
from .exceptions import GitConflictError
from .models import CodeDiff

logger = logging.getLogger(__name__)

class GitManager:
    """Handles Git operations for the Autonomous Software Engineering Framework."""

    def __init__(self, workspace_path: str):
        self._cwd = workspace_path
        if not os.path.exists(os.path.join(self._cwd, ".git")):
            raise ValueError(f"Workspace {self._cwd} is not a valid git repository.")

    def _run(self, args: list[str]) -> str:
        """Run a git command and return stdout."""
        try:
            result = subprocess.run(
                ["git"] + args,
                cwd=self._cwd,
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            raise GitConflictError(f"Git command failed: git {' '.join(args)}\nError: {e.stderr.strip()}") from e

    def create_branch(self, branch_name: str) -> None:
        """Create and checkout a new branch."""
        logger.info(f"Creating branch: {branch_name}")
        self._run(["checkout", "-b", branch_name])

    def create_checkpoint(self, message: str) -> str:
        """Commit all current changes as a checkpoint."""
        logger.info(f"Creating git checkpoint: {message}")
        self._run(["add", "."])
        # Only commit if there are changes
        status = self._run(["status", "--porcelain"])
        if not status:
            return self.get_current_commit()
        
        self._run(["commit", "-m", f"[JARVIS Checkpoint] {message}"])
        return self.get_current_commit()

    def rollback(self, commit_hash: str) -> None:
        """Hard reset to a specific commit."""
        logger.warning(f"Rolling back to {commit_hash}")
        self._run(["reset", "--hard", commit_hash])
        self._run(["clean", "-fd"])

    def get_current_commit(self) -> str:
        """Get the current HEAD commit hash."""
        return self._run(["rev-parse", "HEAD"])

    def get_diff_summary(self, from_commit: str, to_commit: str = "HEAD") -> list[CodeDiff]:
        """Get a summary of changes between two commits."""
        diff_out = self._run(["diff", "--name-status", from_commit, to_commit])
        diffs = []
        for line in diff_out.splitlines():
            if not line.strip():
                continue
            parts = line.split('\t')
            status = parts[0]
            file_path = parts[-1]
            
            change_type = "modify"
            if status.startswith("A"):
                change_type = "create"
            elif status.startswith("D"):
                change_type = "delete"
                
            diffs.append(CodeDiff(
                file_path=file_path,
                change_type=change_type,
            ))
        return diffs

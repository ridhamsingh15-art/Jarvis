"""
Shell Execution Tool — Phase H implementation.

Provides a controlled shell capability.
NEVER exposes raw subprocess.run(user_input) to the LLM.

Security model:
    - Every command must pass ExecutionPolicy before reaching here
    - Commands are classified as SAFE or HIGH_RISK
    - HIGH_RISK commands are denied by default
    - Working directory is restricted to workspace root
    - Environment is filtered (no PATH injection, no credential env vars)
    - Output is capped at MAX_OUTPUT_BYTES
    - Timeout enforced independently of LLM
    - All executions are audit-logged

HIGH_RISK patterns (always denied unless explicitly allowed):
    - rm / del / rmdir with -r/-rf
    - format, mkfs
    - reg add/delete (registry)
    - wget/curl | bash (download + execute)
    - sudo / runas
    - shutdown / reboot / halt
    - net user / passwd (credential modification)
    - any PATH traversal (../)
"""

from __future__ import annotations

import logging
import re
import shlex
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MAX_OUTPUT_BYTES: int = 65_536          # 64 KB
DEFAULT_TIMEOUT_SECONDS: float = 30.0
_SAFE_WORKING_DIRS: list[str] = []     # populated at construction time

# Environment keys that must NEVER be passed through to shell commands
_BLOCKED_ENV_KEYS: frozenset[str] = frozenset({
    "AWS_SECRET_ACCESS_KEY",
    "AWS_SESSION_TOKEN",
    "GOOGLE_APPLICATION_CREDENTIALS",
    "GITHUB_TOKEN",
    "NPM_TOKEN",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "GEMINI_API_KEY",
    "DATABASE_URL",
})

# High-risk command patterns — denied immediately
_HIGH_RISK_PATTERNS: list[re.Pattern] = [p for p in [
    re.compile(r"\brm\s+-[a-z]*r", re.IGNORECASE),       # rm -r / rm -rf
    re.compile(r"\bdel\s+/[sq]", re.IGNORECASE),          # del /s /q
    re.compile(r"\brmdir\s+/[sq]", re.IGNORECASE),        # rmdir /s /q
    re.compile(r"\bformat\b", re.IGNORECASE),             # format disk
    re.compile(r"\bmkfs\b", re.IGNORECASE),               # mkfs
    re.compile(r"\breg\s+(add|delete)\b", re.IGNORECASE), # registry modification
    re.compile(r"\bsudo\b", re.IGNORECASE),               # privilege escalation
    re.compile(r"\brunas\b", re.IGNORECASE),              # privilege escalation
    re.compile(r"\bshutdown\b", re.IGNORECASE),           # system shutdown
    re.compile(r"\breboot\b", re.IGNORECASE),             # reboot
    re.compile(r"\bhalt\b", re.IGNORECASE),               # halt
    re.compile(r"(wget|curl).+\|\s*(bash|sh|python|powershell)", re.IGNORECASE),  # download + execute
    re.compile(r"\bnet\s+user\b", re.IGNORECASE),         # user management
    re.compile(r"\bpasswd\b", re.IGNORECASE),             # password change
    re.compile(r"\.\./", re.IGNORECASE),                  # path traversal
]]


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------


@dataclass
class ShellResult:
    command: str
    return_code: int
    stdout: str
    stderr: str
    timed_out: bool
    blocked: bool
    blocked_reason: str = ""
    latency_ms: float = 0.0

    @property
    def success(self) -> bool:
        return not self.blocked and not self.timed_out and self.return_code == 0


# ---------------------------------------------------------------------------
# ShellTool
# ---------------------------------------------------------------------------


class ShellTool:
    """
    Controlled shell execution with mandatory policy enforcement.

    Must be accessed through ExecutionPolicy before calling execute().
    Registered in the JARVIS tool Registry as 'shell'.
    """

    name = "shell"
    description = "Executes safe shell commands in a controlled environment."

    def __init__(
        self,
        workspace_root: str | Path = ".",
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        max_output_bytes: int = MAX_OUTPUT_BYTES,
        allowed_commands: list[str] | None = None,
    ) -> None:
        self._workspace_root = Path(workspace_root).resolve()
        self._timeout = timeout_seconds
        self._max_output = max_output_bytes
        # Optional allowlist of command prefixes (e.g. ["python", "pip", "git"])
        # If None, no additional allowlist restriction beyond block patterns.
        self._allowed_commands = allowed_commands

    def execute(self, action: str, args: dict[str, Any]) -> str:
        """
        Registry-compatible execute method.

        Registered actions:
            run:  args = {"command": str, "cwd": str (optional)}
        """
        if action == "run":
            command = str(args.get("command", ""))
            cwd_override = args.get("cwd")
            result = self.run(command, cwd_override=cwd_override)
            if result.blocked:
                return f"[BLOCKED] {result.blocked_reason}"
            if result.timed_out:
                return f"[TIMEOUT] Command exceeded {self._timeout}s limit."
            return (
                f"[return_code={result.return_code}]\n"
                f"STDOUT:\n{result.stdout}\n"
                f"STDERR:\n{result.stderr}"
            ).strip()
        raise ValueError(f"Unknown shell action: '{action}'")

    def run(self, command: str, cwd_override: str | None = None) -> ShellResult:
        """
        Execute a shell command after safety checks.

        Args:
            command:      The shell command string.
            cwd_override: Optional working directory. Must be within workspace_root.

        Returns:
            ShellResult with outcome details.
        """
        t0 = time.perf_counter()

        # 1. High-risk pattern check
        block_reason = self._check_high_risk(command)
        if block_reason:
            logger.warning("[SHELL] BLOCKED high-risk command: %s | reason: %s", command[:120], block_reason)
            return ShellResult(
                command=command, return_code=-1, stdout="", stderr="",
                timed_out=False, blocked=True, blocked_reason=block_reason,
            )

        # 2. Allowed command prefix check
        if self._allowed_commands is not None:
            if not self._is_allowed_prefix(command):
                reason = f"Command not in allowlist. Allowed prefixes: {self._allowed_commands}"
                logger.warning("[SHELL] BLOCKED not-in-allowlist: %s", command[:120])
                return ShellResult(
                    command=command, return_code=-1, stdout="", stderr="",
                    timed_out=False, blocked=True, blocked_reason=reason,
                )

        # 3. Resolve working directory
        cwd = self._resolve_cwd(cwd_override)
        if cwd is None:
            reason = f"Working directory '{cwd_override}' is outside workspace root '{self._workspace_root}'"
            logger.warning("[SHELL] BLOCKED invalid cwd: %s", cwd_override)
            return ShellResult(
                command=command, return_code=-1, stdout="", stderr="",
                timed_out=False, blocked=True, blocked_reason=reason,
            )

        # 4. Filter environment
        import os
        filtered_env = {
            k: v for k, v in os.environ.items()
            if k not in _BLOCKED_ENV_KEYS
        }

        # 5. Audit log
        logger.info("[SHELL] EXECUTE cwd=%s cmd=%s", cwd, command[:200])

        # 6. Run
        timed_out = False
        try:
            proc = subprocess.run(
                command,
                shell=True,
                cwd=str(cwd),
                env=filtered_env,
                capture_output=True,
                timeout=self._timeout,
                text=True,
            )
            stdout = proc.stdout[: self._max_output]
            stderr = proc.stderr[: self._max_output // 4]

            latency_ms = (time.perf_counter() - t0) * 1000
            logger.info(
                "[SHELL] DONE return_code=%d latency=%.1fms stdout_bytes=%d",
                proc.returncode, latency_ms, len(stdout),
            )
            return ShellResult(
                command=command, return_code=proc.returncode,
                stdout=stdout, stderr=stderr,
                timed_out=False, blocked=False, latency_ms=latency_ms,
            )
        except subprocess.TimeoutExpired:
            latency_ms = (time.perf_counter() - t0) * 1000
            logger.warning("[SHELL] TIMEOUT after %.1fs: %s", self._timeout, command[:120])
            return ShellResult(
                command=command, return_code=-1, stdout="", stderr="",
                timed_out=True, blocked=False, latency_ms=latency_ms,
            )
        except Exception as exc:  # noqa: BLE001
            latency_ms = (time.perf_counter() - t0) * 1000
            logger.error("[SHELL] ERROR: %s", exc)
            return ShellResult(
                command=command, return_code=-1, stdout="", stderr=str(exc),
                timed_out=False, blocked=False, latency_ms=latency_ms,
            )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _check_high_risk(command: str) -> str:
        """Returns a non-empty reason string if the command matches a high-risk pattern."""
        for pattern in _HIGH_RISK_PATTERNS:
            if pattern.search(command):
                return f"Command matches high-risk pattern: {pattern.pattern}"
        return ""

    def _is_allowed_prefix(self, command: str) -> bool:
        cmd_lower = command.strip().lower()
        return any(cmd_lower.startswith(prefix.lower()) for prefix in self._allowed_commands or [])

    def _resolve_cwd(self, cwd_override: str | None) -> Path | None:
        """Resolve cwd, ensuring it is within workspace_root."""
        if cwd_override is None:
            return self._workspace_root
        try:
            candidate = Path(cwd_override).resolve()
            # Must be within workspace_root
            candidate.relative_to(self._workspace_root)
            return candidate
        except (ValueError, OSError):
            return None

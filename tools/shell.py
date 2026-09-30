"""
Shell Execution Tool — Phase 7G Safe Shell & SWE implementation.

Provides a controlled, workspace-bounded shell capability.
NEVER exposes raw arbitrary shell execution to the LLM.

Security model:
    - Implements BaseTool contract for seamless integration with Registry and ActionRegistry
    - Every command must pass ExecutionPolicy before execution
    - Working directory is strictly restricted to the permitted workspace
    - Path traversal (../, ..\\) and outside-workspace path arguments are blocked
    - Environment is sanitized (all API keys, credentials, and tokens are scrubbed)
    - High-risk patterns (destructive deletions, format, registry, sudo, encoded powershell, download+exec) are blocked
    - Output is capped at MAX_OUTPUT_BYTES
    - Timeout is enforced on every operation
    - All executions are audit-logged
"""

from __future__ import annotations

import logging
import os
import re
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.action_definition import ActionDefinition
from tools.base_tool import BaseTool

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MAX_OUTPUT_BYTES: int = 65_536          # 64 KB
DEFAULT_TIMEOUT_SECONDS: float = 30.0

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
    "OLLAMA_API_KEY",
    "DEEPSEEK_API_KEY",
    "MINIMAX_API_KEY",
    "OPENROUTER_API_KEY",
    "DATABASE_URL",
    "SECRET_KEY",
    "JARVIS_SECRET_KEY",
    "API_KEY",
    "ACCESS_TOKEN",
})

# High-risk command patterns — denied immediately
_HIGH_RISK_PATTERNS: list[re.Pattern] = [
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
    re.compile(r"\|\s*(bash|sh|python|powershell|cmd)", re.IGNORECASE),  # pipe to shell/interpreter
    re.compile(r"\bpowershell.*?(?:-enc|-encodedcommand|-e\b)", re.IGNORECASE),        # encoded powershell
    re.compile(r"\bnet\s+user\b", re.IGNORECASE),         # user management
    re.compile(r"\bpasswd\b", re.IGNORECASE),             # password change
    re.compile(r"\.\.[/\\]|\.\.$", re.IGNORECASE),        # path traversal (../ or ..\ or ..)
]

# Patterns recognized as inherently safe for read-only or software testing
_SAFE_COMMAND_PREFIXES: tuple[str, ...] = (
    "pytest",
    "python -m pytest",
    "py -m pytest",
    "git status",
    "git diff",
    "git log",
    "git branch",
    "echo",
    "dir",
    "type",
    "cat",
    "pip list",
    "pip show",
    "pip check",
)


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


class ShellTool(BaseTool):
    """
    Controlled, workspace-bounded shell execution with mandatory policy enforcement.

    Implements BaseTool to integrate with Registry, Validator, ActionRegistry,
    and ExecutionPolicy.
    """

    @property
    def name(self) -> str:
        """Unique tool identifier."""
        return "shell"

    @property
    def description(self) -> str:
        """Human-readable description for LLM prompts."""
        return "Executes safe, workspace-bounded shell commands and tests."

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
        self._allowed_commands = allowed_commands

    @property
    def workspace_root(self) -> Path:
        return self._workspace_root

    def get_actions(self) -> dict[str, ActionDefinition]:
        """Return available actions and their structured definitions."""
        return {
            "run": ActionDefinition(
                name="run",
                description="Executes a safe shell command within the permitted workspace.",
                required_args=[],
                optional_args=["command", "cmd", "executable", "args", "arguments", "params", "parameters", "cwd", "timeout"],
            ),
            "execute": ActionDefinition(
                name="execute",
                description="Executes a structured command within the permitted workspace.",
                required_args=[],
                optional_args=["executable", "command", "cmd", "args", "arguments", "params", "parameters", "cwd", "timeout"],
            ),
        }

    def execute(self, action: str, args: dict[str, Any]) -> str:
        """
        Registry-compatible execute method.

        Registered actions:
            run:      args = {"command": str | list, "cwd": str (optional), "timeout": float (optional)}
            execute:  args = {"executable": str, "args": list | str, "cwd": str (optional)}
        """
        def _to_cmd_str(val: Any) -> str:
            if isinstance(val, (list, tuple)):
                return " ".join(str(x) for x in val)
            s = str(val or "").strip()
            if s.startswith("[") and s.endswith("]"):
                try:
                    import ast
                    parsed = ast.literal_eval(s)
                    if isinstance(parsed, (list, tuple)):
                        return " ".join(str(x) for x in parsed)
                except Exception:
                    pass
            return s

        if action in ("run", "shell_run"):
            command = _to_cmd_str(args.get("command") or args.get("cmd") or args.get("executable"))
            extra_args = args.get("args") or args.get("arguments") or args.get("params") or args.get("parameters")
            if extra_args:
                extra_str = _to_cmd_str(extra_args)
                command = f"{command} {extra_str}".strip()
            cwd_override = args.get("cwd")
            timeout_override = args.get("timeout")
            result = self.run(command, cwd_override=cwd_override, timeout=timeout_override)
            if result.blocked:
                from core.exceptions import ExecutionError
                raise ExecutionError(f"Operation blocked: {result.blocked_reason}")
            if result.timed_out:
                from core.exceptions import ExecutionError
                raise ExecutionError(f"Command timed out after {timeout_override or self._timeout}s.")
            return (
                f"[return_code={result.return_code}]\n"
                f"STDOUT:\n{result.stdout}\n"
                f"STDERR:\n{result.stderr}"
            ).strip()

        if action == "execute":
            exe = _to_cmd_str(args.get("executable") or args.get("command") or args.get("cmd"))
            extra_args = args.get("args") or args.get("arguments") or args.get("params") or args.get("parameters")
            if extra_args:
                cmd_str = f"{exe} {_to_cmd_str(extra_args)}".strip()
            else:
                cmd_str = exe
            return self.execute("run", {"command": cmd_str, "cwd": args.get("cwd"), "timeout": args.get("timeout")})

        raise ValueError(f"Unknown shell action: '{action}'")

    def run(
        self,
        command: str,
        cwd_override: str | None = None,
        timeout: float | None = None,
    ) -> ShellResult:
        """
        Execute a shell command after safety and workspace validation.

        Args:
            command:      The shell command string.
            cwd_override: Optional working directory. Must be within workspace_root.
            timeout:      Optional operation timeout in seconds.

        Returns:
            ShellResult with outcome details.
        """
        t0 = time.perf_counter()
        effective_timeout = float(timeout) if timeout is not None else self._timeout

        # 1. High-risk pattern & path-escape check
        block_reason = self._check_high_risk(command)
        if block_reason:
            logger.warning("[SHELL] BLOCKED: %s | reason: %s", command[:120], block_reason)
            return ShellResult(
                command=command, return_code=-1, stdout="", stderr="",
                timed_out=False, blocked=True, blocked_reason=block_reason,
            )

        # 2. Workspace boundary escape check in command arguments
        workspace_reason = self._check_workspace_boundary(command)
        if workspace_reason:
            logger.warning("[SHELL] BLOCKED workspace violation: %s", workspace_reason)
            return ShellResult(
                command=command, return_code=-1, stdout="", stderr="",
                timed_out=False, blocked=True, blocked_reason=workspace_reason,
            )

        # 3. Allowed command prefix check
        if self._allowed_commands is not None:
            if not self._is_allowed_prefix(command):
                reason = f"Command not in allowlist. Allowed prefixes: {self._allowed_commands}"
                logger.warning("[SHELL] BLOCKED not-in-allowlist: %s", command[:120])
                return ShellResult(
                    command=command, return_code=-1, stdout="", stderr="",
                    timed_out=False, blocked=True, blocked_reason=reason,
                )

        # 4. Resolve working directory
        cwd = self._resolve_cwd(cwd_override)
        if cwd is None:
            reason = f"Working directory '{cwd_override}' is outside workspace root '{self._workspace_root}'"
            logger.warning("[SHELL] BLOCKED invalid cwd: %s", cwd_override)
            return ShellResult(
                command=command, return_code=-1, stdout="", stderr="",
                timed_out=False, blocked=True, blocked_reason=reason,
            )

        # 5. Filter environment variables (credential sanitization)
        filtered_env = {
            k: v for k, v in os.environ.items()
            if not any(blocked.lower() in k.lower() for blocked in _BLOCKED_ENV_KEYS)
        }
        venv_scripts = str(Path(sys.executable).parent)
        current_path = filtered_env.get("PATH", "")
        if venv_scripts.lower() not in current_path.lower():
            filtered_env["PATH"] = f"{venv_scripts};{current_path}"

        # Resolve pytest to current python interpreter for hermetic execution
        exec_cmd = command.strip()
        if exec_cmd.startswith("pytest ") or exec_cmd == "pytest":
            exec_cmd = f'"{sys.executable}" -m pytest' + exec_cmd[6:]

        # 6. Audit log
        logger.info("[SHELL] EXECUTE cwd=%s cmd=%s", cwd, command[:200])

        # 7. Run subprocess with bounded output and timeout
        try:
            proc = subprocess.run(
                exec_cmd,
                shell=True,
                cwd=str(cwd),
                env=filtered_env,
                capture_output=True,
                timeout=effective_timeout,
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
            logger.warning("[SHELL] TIMEOUT after %.1fs: %s", effective_timeout, command[:120])
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
    # Security and boundary helpers
    # ------------------------------------------------------------------

    @classmethod
    def check_high_risk(cls, command: str) -> str:
        """Expose high risk check for ExecutionPolicy and other callers."""
        for pattern in _HIGH_RISK_PATTERNS:
            if pattern.search(command):
                if r"\.\." in pattern.pattern:
                    return f"Path traversal detected: {pattern.pattern}"
                return f"Command matches high-risk pattern: {pattern.pattern}"
        return ""

    def _check_high_risk(self, command: str) -> str:
        return self.check_high_risk(command)

    def _check_workspace_boundary(self, command: str) -> str:
        """Detect attempts to access or modify paths outside the permitted workspace."""
        # Find potential file paths in command arguments
        tokens = command.strip().split()
        if len(tokens) <= 1:
            return ""

        py_prefix = str(Path(sys.executable).parent).lower()

        for token in tokens[1:]:
            clean_token = token.strip("'\"")
            # Skip flags
            if clean_token.startswith("-") or clean_token.startswith("/"):
                # Windows flag e.g. /q, /s or flag like -v
                if not (len(clean_token) > 2 and clean_token[1] == ":" and clean_token[0].isalpha()):
                    continue

            # Check if this token is an absolute path or path traversal
            if (".." in clean_token and ("/" in clean_token or "\\" in clean_token)) or clean_token.startswith(".."):
                return f"Path traversal detected in argument '{clean_token}'"

            try:
                candidate = Path(clean_token)
                if candidate.is_absolute():
                    resolved = candidate.resolve()
                    # Allow active Python venv/interpreter paths
                    if str(resolved).lower().startswith(py_prefix):
                        continue
                    # Check if relative to workspace
                    try:
                        resolved.relative_to(self._workspace_root)
                    except ValueError:
                        return f"Argument path '{clean_token}' is outside workspace '{self._workspace_root}'"
            except Exception:
                continue

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
            candidate.relative_to(self._workspace_root)
            return candidate
        except (ValueError, OSError):
            return None

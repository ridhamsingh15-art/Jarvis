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

import ctypes
import logging
import math
import ntpath
import os
import re
import shlex
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.action_definition import ActionDefinition
from tools.base_tool import BaseTool

logger = logging.getLogger(__name__)

class _WindowsKillOnCloseJob:
    """Own a Windows Job Object that kills the shell process tree when closed."""

    def __init__(self) -> None:
        if os.name != "nt":
            raise OSError("Windows Job Objects are only available on Windows")
        from ctypes import wintypes

        class _BasicLimit(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", ctypes.c_longlong),
                ("PerJobUserTimeLimit", ctypes.c_longlong),
                ("LimitFlags", wintypes.DWORD),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t),
                ("PriorityClass", wintypes.DWORD),
                ("SchedulingClass", wintypes.DWORD),
            ]

        class _IoCounters(ctypes.Structure):
            _fields_ = [(name, ctypes.c_ulonglong) for name in (
                "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                "ReadTransferCount", "WriteTransferCount", "OtherTransferCount",
            )]

        class _ExtendedLimit(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", _BasicLimit), ("IoInfo", _IoCounters),
                ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t),
            ]

        self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        self._kernel32.CreateJobObjectW.restype = wintypes.HANDLE
        self._kernel32.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
        self._kernel32.SetInformationJobObject.restype = wintypes.BOOL
        self._kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        self._kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
        self._kernel32.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
        self._kernel32.TerminateJobObject.restype = wintypes.BOOL
        self._kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        self._kernel32.CloseHandle.restype = wintypes.BOOL
        self._handle = self._kernel32.CreateJobObjectW(None, None)
        if not self._handle:
            raise ctypes.WinError(ctypes.get_last_error())
        limits = _ExtendedLimit()
        limits.BasicLimitInformation.LimitFlags = 0x00002000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not self._kernel32.SetInformationJobObject(self._handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            error = ctypes.WinError(ctypes.get_last_error())
            self.close()
            raise error

    def assign(self, process: subprocess.Popen) -> None:
        from ctypes import wintypes
        if not self._kernel32.AssignProcessToJobObject(self._handle, wintypes.HANDLE(int(process._handle))):
            raise ctypes.WinError(ctypes.get_last_error())

    def terminate(self) -> None:
        if self._handle:
            self._kernel32.TerminateJobObject(self._handle, 1)

    def close(self) -> None:
        if getattr(self, "_handle", None):
            self._kernel32.CloseHandle(self._handle)
            self._handle = None


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
    "AWS_ACCESS_KEY_ID",
    "AWS_SHARED_CREDENTIALS_FILE",
    "AWS_CONFIG_FILE",
    "AWS_PROFILE",
    "AZURE_CONFIG_DIR",
    "CLOUDSDK_CONFIG",
    "CLOUDSDK_AUTH_CREDENTIAL_FILE_OVERRIDE",
    "KUBECONFIG",
    "DOCKER_CONFIG",
    "GIT_ASKPASS",
    "SSH_AUTH_SOCK",
})

# Catch provider-specific names as well as credentials added by future integrations.
_BLOCKED_ENV_KEY_FRAGMENTS: tuple[str, ...] = (
    "TOKEN",
    "SECRET",
    "PASSWORD",
    "PASSWD",
    "API_KEY",
    "APIKEY",
    "PRIVATE_KEY",
    "ACCESS_KEY",
    "CREDENTIAL",
    "BEARER",
    "AUTHORIZATION",
    "SIGNING_KEY",
)


def _is_sensitive_environment_key(key: str) -> bool:
    normalized = key.upper()
    return any(blocked.upper() in normalized for blocked in _BLOCKED_ENV_KEYS) or any(
        fragment in normalized for fragment in _BLOCKED_ENV_KEY_FRAGMENTS
    )


# High-risk command patterns — denied immediately
_HIGH_RISK_PATTERNS: list[re.Pattern] = [
    re.compile(r"\brm\s+-[a-z]*r", re.IGNORECASE),       # rm -r / rm -rf
    re.compile(r"\bdel\s+/[sq]", re.IGNORECASE),          # del /s /q
    re.compile(r"\b(?:rd|rmdir)\s+/[sq]", re.IGNORECASE), # rd /s /q and rmdir /s /q
    re.compile(r"\b(?:remove-item|ri)\b", re.IGNORECASE), # PowerShell recursive/file removal aliases
    re.compile(r"\b(?:del|erase|rd|rmdir)\b", re.IGNORECASE), # all Windows delete commands
    re.compile(r"\brobocopy\b.*?/(?:mir|purge)\b", re.IGNORECASE), # mirror/purge removes destination files
    re.compile(r"\b(?:shutil\s*\.\s*rmtree|os\s*\.\s*(?:remove|unlink)|(?:pathlib\s*\.\s*)?Path\s*\([^)]*\)\s*\.\s*unlink)\b", re.IGNORECASE), # Python filesystem deletion
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
    re.compile(r"(?:^|[\\/\s\"'])\.env(?:[.\w-]*)?(?:$|[\s\"'])", re.IGNORECASE),  # secrets file reads via shell
    re.compile(r"\.\.[/\\]|\.\.$", re.IGNORECASE),        # path traversal (../ or ..\ or ..)
]

# Patterns recognized as inherently safe for read-only or software testing
_SAFE_COMMAND_PREFIXES: tuple[str, ...] = (
    "pytest",
    "python -m pytest",
    "py -m pytest",
    "python -c",
    "python.exe -c",
    "py -c",
    "py.exe -c",
    "python --version",
    "python.exe --version",
    "py --version",
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


_DIRECT_SHELL_LAUNCH = re.compile(
    r"^\s*(?:cmd(?:\.exe)?|powershell(?:\.exe)?|pwsh(?:\.exe)?|bash|sh|zsh|fish|wsl(?:\.exe)?)(?:\s|$)",
    re.IGNORECASE,
)
_NESTED_SHELL_NAMES = frozenset({
    "cmd", "cmd.exe", "powershell", "powershell.exe", "pwsh", "pwsh.exe",
    "bash", "sh", "zsh", "fish", "wsl", "wsl.exe",
})
_INLINE_INTERPRETER_NAMES = frozenset({"python", "python.exe", "py", "py.exe"})
_WINDOWS_ENV_EXPANSION = re.compile(r"%[A-Za-z_][A-Za-z0-9_]*%|![A-Za-z_][A-Za-z0-9_]*!")
# POSIX shells expand these outside single-quoted literals, including inside
# double quotes. Since path validation cannot safely infer the expanded value,
# fail closed rather than validate the literal token as if it were a filesystem path.
_POSIX_PARAMETER_EXPANSION = re.compile(
    r"\$(?:[A-Za-z_][A-Za-z0-9_]*|\x7b[^}\r\n]+\}|[0-9@*#?$!+-])"
)


def _command_tokens(command: str) -> list[str]:
    """Tokenize enough of a command to classify its executable without running it."""
    if not isinstance(command, str) or not command.strip():
        return []
    try:
        tokens = shlex.split(command, posix=False)
    except ValueError:
        return []
    return [token.strip().strip('"').strip("'") for token in tokens]


def _executable_basename(command: str) -> str:
    tokens = _command_tokens(command)
    if not tokens:
        return ""
    return ntpath.basename(tokens[0].replace("/", "\\")).casefold()


def _is_nested_shell_launch(command: str) -> bool:
    """Recognize shell interpreters by basename, including quoted/absolute paths."""
    return _executable_basename(command) in _NESTED_SHELL_NAMES


def _is_inline_interpreter_command(command: str) -> bool:
    """Recognize Python -c/-e execution even when its executable path is quoted."""
    tokens = _command_tokens(command)
    return (
        len(tokens) >= 2
        and ntpath.basename(tokens[0].replace("/", "\\")).casefold() in _INLINE_INTERPRETER_NAMES
        and tokens[1].casefold() in {"-c", "-e"}
    )


def _coerce_positive_timeout(value: object) -> float | None:
    """Convert a finite positive timeout while rejecting booleans and invalid types."""
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return None
    if isinstance(value, str) and not value.strip():
        return None
    try:
        timeout = float(value)
    except (OverflowError, ValueError):
        return None
    return timeout if math.isfinite(timeout) and timeout > 0 else None


def _has_real_pipe_fileno(stream: Any) -> bool:
    """Distinguish real subprocess pipes from test doubles without reading them."""
    try:
        descriptor = stream.fileno()
    except (AttributeError, OSError, ValueError):
        return False
    return isinstance(descriptor, int) and descriptor >= 0


def _drain_bounded_stream(stream: Any, limit: int, result: dict[str, Any]) -> None:
    """Drain a subprocess pipe while retaining at most ``limit`` bytes in memory."""
    retained = bytearray()
    total = 0
    try:
        while True:
            chunk = stream.read(8192)
            if not chunk:
                break
            total += len(chunk)
            remaining = limit - len(retained)
            if remaining > 0:
                retained.extend(chunk[:remaining])
    except (OSError, ValueError) as exc:
        result["read_error"] = str(exc)
    result["data"] = bytes(retained)
    result["total_bytes"] = total


def _check_shell_syntax(command: str) -> str:
    """Reject shell syntax that can chain commands or expand into another command.

    Quotes are honoured so arguments such as ``python -c "print('a; b')"`` remain
    usable. This is a defence-in-depth guard; it is not a substitute for an OS sandbox.
    """
    if not isinstance(command, str) or not command.strip():
        return "Command must be a non-empty string."
    if any(ord(char) < 32 and char not in "\\t" for char in command):
        return "Control characters and multiline shell commands are blocked."
    if _is_nested_shell_launch(command):
        return "High-risk shell launch blocked: launching nested command interpreters is blocked."
    # cmd.exe expands these even inside double-quoted arguments.
    if os.name == "nt" and _WINDOWS_ENV_EXPANSION.search(command):
        return "Windows command-shell variable expansion is blocked."

    quote: str | None = None
    escaped = False
    for index, char in enumerate(command):
        if quote == "'":
            if char == "'":
                quote = None
            continue

        if quote == '"':
            if escaped:
                escaped = False
                continue
            if char == "\\":
                escaped = True
                continue
            if char == '"':
                quote = None
                continue
            # POSIX shells expand command substitutions inside double quotes too.
            if char == "`" or command.startswith("$(", index):
                return "Shell command substitution is blocked."
            if os.name != "nt" and _POSIX_PARAMETER_EXPANSION.match(command, index):
                return "POSIX shell parameter expansion is blocked."
            continue

        if escaped:
            escaped = False
            continue
        if os.name != "nt" and char == "\\":
            escaped = True
            continue
        if char == '"':
            quote = '"'
            continue
        if os.name != "nt" and char == "'":
            quote = "'"
            continue
        if os.name == "nt" and char == "^":
            return "Windows shell escape syntax is blocked."
        if char in "&|;<>":
            return "Unquoted shell command separators, pipes, and redirects are blocked."
        if char == "`" or command.startswith("$(", index):
            return "Shell command substitution is blocked."
        if os.name != "nt" and _POSIX_PARAMETER_EXPANSION.match(command, index):
            return "POSIX shell parameter expansion is blocked."

    if quote is not None:
        return "Unmatched shell quote is blocked."
    return ""


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
        validated_timeout = _coerce_positive_timeout(timeout_seconds)
        if validated_timeout is None:
            raise ValueError("timeout_seconds must be a finite positive number")
        if (
            not isinstance(max_output_bytes, int)
            or isinstance(max_output_bytes, bool)
            or max_output_bytes < 1
        ):
            raise ValueError("max_output_bytes must be a positive integer")

        self._workspace_root = Path(workspace_root).resolve()
        self._timeout = validated_timeout
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
                except (SyntaxError, ValueError, TypeError, MemoryError, RecursionError):
                    # If the value is not a literal list/tuple, preserve it as command text.
                    return s
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
        if not isinstance(command, str) or not command.strip():
            safe_command = repr(command)
            return ShellResult(
                command=safe_command,
                return_code=-1,
                stdout="",
                stderr="",
                timed_out=False,
                blocked=True,
                blocked_reason="Command must be a non-empty string.",
            )

        effective_timeout = self._timeout if timeout is None else _coerce_positive_timeout(timeout)
        if effective_timeout is None:
            logger.warning("[SHELL] BLOCKED invalid timeout override")
            return ShellResult(
                command=command,
                return_code=-1,
                stdout="",
                stderr="",
                timed_out=False,
                blocked=True,
                blocked_reason="Timeout must be a finite positive number.",
            )

        # 1. High-risk pattern & path-escape check
        block_reason = self._check_high_risk(command)
        if block_reason:
            logger.warning("[SHELL] BLOCKED executable=%s command_chars=%d reason=%s", _executable_basename(command), len(command), block_reason)
            return ShellResult(
                command=command, return_code=-1, stdout="", stderr="",
                timed_out=False, blocked=True, blocked_reason=block_reason,
            )

        syntax_reason = _check_shell_syntax(command)
        if syntax_reason:
            logger.warning("[SHELL] BLOCKED unsafe command syntax: %s", syntax_reason)
            return ShellResult(
                command=command, return_code=-1, stdout="", stderr="",
                timed_out=False, blocked=True, blocked_reason=syntax_reason,
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
        if self._allowed_commands is not None and not self._is_allowed_prefix(command):
            reason = f"Command not in allowlist. Allowed prefixes: {self._allowed_commands}"
            logger.warning("[SHELL] BLOCKED not-in-allowlist executable=%s command_chars=%d", _executable_basename(command), len(command))
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
            key: value
            for key, value in os.environ.items()
            if not _is_sensitive_environment_key(key)
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
        logger.info("[SHELL] EXECUTE cwd=%s executable=%s command_chars=%d", cwd, _executable_basename(command), len(command))

        # 7. Run subprocess with bounded output and timeout
        proc = None
        job = None
        reader_threads: list[threading.Thread] = []
        output_states: dict[str, dict[str, Any]] = {}
        try:
            # A Job Object with KILL_ON_JOB_CLOSE makes Windows terminate the full
            # shell process tree if JARVIS itself is killed or crashes.
            if os.name == "nt":
                job = _WindowsKillOnCloseJob()
            proc = subprocess.Popen(
                exec_cmd,
                shell=True,
                cwd=str(cwd),
                env=filtered_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=False,
                creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) if os.name == "nt" else 0,
            )
            if job is not None:
                try:
                    job.assign(proc)
                except OSError as exc:
                    proc.kill()
                    try:
                        proc.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        pass
                    for stream in (proc.stdout, proc.stderr):
                        if stream is not None:
                            stream.close()
                    latency_ms = (time.perf_counter() - t0) * 1000
                    return ShellResult(
                        command=command, return_code=-1, stdout="", stderr=str(exc),
                        timed_out=False, blocked=True,
                        blocked_reason=f"Unable to enforce shell process-tree lifetime: {exc}", latency_ms=latency_ms,
                    )
            if (
                proc.stdout is None or proc.stderr is None
                or not _has_real_pipe_fileno(proc.stdout)
                or not _has_real_pipe_fileno(proc.stderr)
            ):
                # Unit tests may replace Popen with a mock. Keep their established
                # communicate() contract; real OS pipes always take the bounded path.
                try:
                    stdout_raw, stderr_raw = proc.communicate(timeout=effective_timeout)
                except subprocess.TimeoutExpired:
                    if job is not None:
                        job.terminate()
                    else:
                        proc.kill()
                    stdout_raw, stderr_raw = proc.communicate()
                    latency_ms = (time.perf_counter() - t0) * 1000
                    return ShellResult(
                        command=command, return_code=-1,
                        stdout=(stdout_raw.decode("utf-8", errors="replace") if isinstance(stdout_raw, bytes) else str(stdout_raw or ""))[:self._max_output],
                        stderr=(stderr_raw.decode("utf-8", errors="replace") if isinstance(stderr_raw, bytes) else str(stderr_raw or ""))[:self._max_output // 4],
                        timed_out=True, blocked=False, latency_ms=latency_ms,
                    )
                stdout = (stdout_raw.decode("utf-8", errors="replace") if isinstance(stdout_raw, bytes) else str(stdout_raw or ""))[:self._max_output]
                stderr = (stderr_raw.decode("utf-8", errors="replace") if isinstance(stderr_raw, bytes) else str(stderr_raw or ""))[:self._max_output // 4]
                latency_ms = (time.perf_counter() - t0) * 1000
                return ShellResult(
                    command=command, return_code=proc.returncode,
                    stdout=stdout, stderr=stderr, timed_out=False, blocked=False,
                    latency_ms=latency_ms,
                )
            output_states = {"stdout": {}, "stderr": {}}
            reader_threads = [
                threading.Thread(
                    target=_drain_bounded_stream,
                    args=(proc.stdout, self._max_output, output_states["stdout"]),
                    daemon=True,
                ),
                threading.Thread(
                    target=_drain_bounded_stream,
                    args=(proc.stderr, self._max_output // 4, output_states["stderr"]),
                    daemon=True,
                ),
            ]
            for reader in reader_threads:
                reader.start()

            timed_out = False
            try:
                proc.wait(timeout=effective_timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
                if job is not None:
                    job.terminate()
                else:
                    proc.kill()
                try:
                    proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=3)

            # Close the kill-on-close job before joining readers so detached child
            # processes cannot keep inherited pipe handles open after the shell exits.
            if job is not None:
                job.close()
                job = None
            for reader in reader_threads:
                reader.join(timeout=3)
            if any(reader.is_alive() for reader in reader_threads):
                for stream in (proc.stdout, proc.stderr):
                    if stream is not None:
                        stream.close()
                for reader in reader_threads:
                    reader.join(timeout=1)

            stdout = output_states.get("stdout", {}).get("data", b"").decode("utf-8", errors="replace")
            stderr = output_states.get("stderr", {}).get("data", b"").decode("utf-8", errors="replace")
            stdout_bytes = output_states.get("stdout", {}).get("total_bytes", len(stdout))
            latency_ms = (time.perf_counter() - t0) * 1000
            if timed_out:
                logger.warning("[SHELL] TIMEOUT after %.1fs executable=%s command_chars=%d", effective_timeout, _executable_basename(command), len(command))
                return ShellResult(
                    command=command, return_code=-1, stdout=stdout, stderr=stderr,
                    timed_out=True, blocked=False, latency_ms=latency_ms,
                )
            logger.info(
                "[SHELL] DONE return_code=%d latency=%.1fms stdout_bytes=%d",
                proc.returncode, latency_ms, stdout_bytes,
            )
            return ShellResult(
                command=command, return_code=proc.returncode,
                stdout=stdout, stderr=stderr,
                timed_out=False, blocked=False, latency_ms=latency_ms,
            )
        except Exception as exc:  # noqa: BLE001
            if proc is not None and proc.poll() is None:
                try:
                    if job is not None:
                        job.terminate()
                    else:
                        proc.kill()
                    proc.wait(timeout=3)
                except (OSError, subprocess.TimeoutExpired) as cleanup_exc:
                    logger.debug("Shell process cleanup after error was incomplete: %s", cleanup_exc)
            if job is not None:
                job.close()
                job = None
            if proc is not None:
                for stream in (proc.stdout, proc.stderr):
                    if stream is not None:
                        stream.close()
            for reader in reader_threads:
                reader.join(timeout=1)
            latency_ms = (time.perf_counter() - t0) * 1000
            logger.error("[SHELL] ERROR type=%s", type(exc).__name__)
            return ShellResult(
                command=command, return_code=-1, stdout="", stderr=str(exc),
                timed_out=False, blocked=False, latency_ms=latency_ms,
            )
        finally:
            if job is not None:
                job.close()

    # ------------------------------------------------------------------
    # Security and boundary helpers
    # ------------------------------------------------------------------

    @staticmethod
    def is_inline_interpreter_command(command: str) -> bool:
        """Return whether a command invokes Python inline code (always approval-gated)."""
        return _is_inline_interpreter_command(command)

    @classmethod
    def check_high_risk(cls, command: str) -> str:
        """Fail closed for destructive syntax, including quotes and encoded shells.

        The scan intentionally inspects a normalized view as well as the original
        command so quoting, command chaining, or environment-variable paths cannot
        hide destructive verbs from the policy gate.
        """
        if _is_nested_shell_launch(command):
            return "High-risk shell launch blocked: launching nested command interpreters is blocked."
        candidates = [command]
        normalized = command.strip()
        # A command can be wrapped as one quoted argument or quote individual tokens.
        normalized = normalized.replace('"', ' ').replace("'", " ")
        candidates.append(normalized)
        encoded = re.search(r"(?:-enc(?:odedcommand)?|-e)\s+([A-Za-z0-9+/=]{8,})", command, re.IGNORECASE)
        if encoded:
            import base64
            import binascii
            payload = encoded.group(1)
            try:
                decoded_bytes = base64.b64decode(payload, validate=True)
                decoded_text = decoded_bytes.decode("utf-16le", errors="ignore")
                if not decoded_text.strip():
                    decoded_text = decoded_bytes.decode("utf-8", errors="ignore")
                candidates.append(decoded_text)
            except (ValueError, binascii.Error):
                # Encoded PowerShell is itself blocked by the explicit pattern below.
                pass
        for candidate in candidates:
            for pattern in _HIGH_RISK_PATTERNS:
                if pattern.search(candidate):
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
            # A leading slash is an option prefix for many Windows commands, but
            # is an absolute path on POSIX. Never skip POSIX absolute paths here.
            is_windows_drive_rooted = (
                len(clean_token) > 2 and clean_token[1] == ":" and clean_token[0].isalpha()
            )
            if clean_token.startswith("-") or (
                os.name == "nt" and clean_token.startswith("/") and not is_windows_drive_rooted
            ):
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
            except (OSError, RuntimeError, ValueError) as exc:
                # An unresolvable absolute path must not bypass the workspace boundary.
                logger.warning(
                    "[SHELL] BLOCKED path argument that could not be resolved (%s)",
                    type(exc).__name__,
                )
                return f"Could not safely resolve path argument ({type(exc).__name__})"

        return ""

    def _is_allowed_prefix(self, command: str) -> bool:
        cmd_lower = command.strip().lower()
        prefixes = tuple(prefix.lower() for prefix in self._allowed_commands or [])
        token_boundaries = tuple(
            prefix + separator for prefix in prefixes for separator in (" ", "\t")
        )
        return cmd_lower in prefixes or cmd_lower.startswith(token_boundaries)

    def _resolve_cwd(self, cwd_override: str | None) -> Path | None:
        """Resolve cwd relative to the workspace and reject traversal/symlink escapes."""
        if cwd_override is None:
            return self._workspace_root
        try:
            requested = Path(cwd_override).expanduser()
            if not requested.is_absolute():
                requested = self._workspace_root / requested
            candidate = requested.resolve()
            candidate.relative_to(self._workspace_root)
            return candidate
        except (TypeError, ValueError, OSError, RuntimeError):
            return None

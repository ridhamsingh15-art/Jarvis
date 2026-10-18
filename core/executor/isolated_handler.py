"""Process-isolated execution for registered, serializable BaseTool actions.

Only trusted application code constructs these handlers. User arguments are sent as
JSON; the tool object/action descriptor is serialized separately by the parent.
"""
from __future__ import annotations

import base64
import json
import math
import os
import pickle
import signal
import subprocess
import sys
from pathlib import Path
from typing import Any

_RESULT_PREFIX = "__JARVIS_ISOLATED_RESULT__"


class IsolatedHandlerTimeout(RuntimeError):
    """A bounded worker was terminated; its external outcome must be reconciled."""


class IsolatedHandlerError(RuntimeError):
    """The isolated worker failed or returned an invalid protocol response."""


class _WindowsProcessTreeJob:
    """Contain a worker tree during execution without killing successful detached apps."""

    def __init__(self) -> None:
        import ctypes
        from ctypes import wintypes

        self._ctypes = ctypes
        self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        self._kernel32.CreateJobObjectW.restype = wintypes.HANDLE
        self._kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        self._kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
        self._kernel32.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
        self._kernel32.TerminateJobObject.restype = wintypes.BOOL
        self._kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        self._kernel32.CloseHandle.restype = wintypes.BOOL
        self._handle = self._kernel32.CreateJobObjectW(None, None)
        if not self._handle:
            raise ctypes.WinError(ctypes.get_last_error())

    def assign(self, process: subprocess.Popen[str]) -> None:
        from ctypes import wintypes

        if not self._kernel32.AssignProcessToJobObject(
            self._handle, wintypes.HANDLE(int(process._handle))
        ):
            raise self._ctypes.WinError(self._ctypes.get_last_error())

    def terminate(self) -> None:
        if self._handle and not self._kernel32.TerminateJobObject(self._handle, 1):
            raise self._ctypes.WinError(self._ctypes.get_last_error())

    def close(self) -> None:
        if self._handle:
            self._kernel32.CloseHandle(self._handle)
            self._handle = None


class IsolatedToolHandler:
    """Run one BaseTool action in a killable child process with a strict deadline."""

    def __init__(
        self,
        tool: Any,
        action: str,
        *,
        timeout_seconds: float = 25.0,
        mode: str = "tool",
        project_root: str | Path | None = None,
    ) -> None:
        if (
            isinstance(timeout_seconds, bool)
            or not isinstance(timeout_seconds, (int, float))
            or not math.isfinite(timeout_seconds)
            or timeout_seconds <= 0
        ):
            raise ValueError("timeout_seconds must be a finite positive number")
        if mode not in {"tool", "shell_structured"}:
            raise ValueError(f"Unsupported isolated tool mode: {mode}")
        self.tool = tool
        self.action = action
        self.timeout_seconds = float(timeout_seconds)
        # ExecutionEngine/Agent must not return before this worker's own deadline.
        self.execution_timeout_seconds = self.timeout_seconds
        self.mode = mode
        self.project_root = Path(project_root or Path(__file__).resolve().parents[2]).resolve()

    def validate_configuration(self) -> None:
        """Validate the trusted descriptor before accepting a registration."""
        required_method = "run" if self.mode == "shell_structured" else "execute"
        if not callable(getattr(self.tool, required_method, None)):
            raise IsolatedHandlerError(
                f"Isolated {self.mode} handler tool must expose callable {required_method}()."
            )
        try:
            pickle.dumps((self.tool, self.action, self.mode), protocol=pickle.HIGHEST_PROTOCOL)
        except Exception as exc:
            raise IsolatedHandlerError(
                f"Handler could not be safely serialized for process isolation: "
                f"{type(exc).__name__}: {exc}"
            ) from exc

    def __call__(self, _context: Any = None, **kwargs: Any) -> Any:
        try:
            trusted_descriptor = base64.b64encode(
                pickle.dumps((self.tool, self.action, self.mode), protocol=pickle.HIGHEST_PROTOCOL)
            ).decode("ascii")
            payload = json.dumps({"descriptor": trusted_descriptor, "args": kwargs}, ensure_ascii=False)
        except Exception as exc:
            raise IsolatedHandlerError(
                f"Handler could not be safely serialized for process isolation: {type(exc).__name__}: {exc}"
            ) from exc

        env = os.environ.copy()
        search_paths = [str(self.project_root)]
        for item in sys.path:
            if not item:
                continue
            try:
                resolved = Path(item).resolve()
                resolved.relative_to(self.project_root)
            except (OSError, ValueError):
                continue
            if str(resolved) not in search_paths:
                search_paths.append(str(resolved))
        inherited = env.get("PYTHONPATH", "")
        if inherited:
            search_paths.append(inherited)
        env["PYTHONPATH"] = os.pathsep.join(search_paths)
        env["PYTHONUTF8"] = "1"

        process = subprocess.Popen(
            [sys.executable, "-m", "core.executor.isolated_tool_worker"],
            cwd=str(self.project_root),
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=False,
            start_new_session=(os.name != "nt"),
        )
        job = None
        if os.name == "nt":
            try:
                if getattr(self.tool, "name", "") in {"browser", "windows"}:
                    # These actions intentionally launch a visible application. A
                    # kill-on-close job would also terminate that successful result.
                    job = _WindowsProcessTreeJob()
                else:
                    # Shell/Codex/custom tools must not leave child processes behind
                    # if the JARVIS parent crashes; kill-on-close provides that guarantee.
                    from tools.shell import _WindowsKillOnCloseJob

                    job = _WindowsKillOnCloseJob()
                job.assign(process)
            except Exception as exc:
                try:
                    process.kill()
                    process.wait(timeout=5)
                except (OSError, subprocess.TimeoutExpired):
                    pass
                if job is not None:
                    job.close()
                raise IsolatedHandlerError(
                    f"Could not establish Windows process-tree containment: {type(exc).__name__}: {exc}"
                ) from exc

        try:
            stdout, stderr = process.communicate(payload, timeout=self.timeout_seconds)
        except subprocess.TimeoutExpired as exc:
            if job is not None:
                try:
                    job.terminate()
                except OSError:
                    pass
            elif os.name != "nt":
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except (ProcessLookupError, PermissionError):
                    pass
            try:
                process.kill()
            except OSError:
                pass
            try:
                process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                pass
            raise IsolatedHandlerTimeout(
                f"Handler timed out after {self.timeout_seconds:g}s; OUTCOME UNKNOWN. "
                "The isolated worker was terminated. Reconcile external state and independently "
                "verify the expected postcondition before retrying."
            ) from exc
        finally:
            if job is not None:
                job.close()

        protocol_lines = [line[len(_RESULT_PREFIX):] for line in stdout.splitlines() if line.startswith(_RESULT_PREFIX)]
        if process.returncode != 0 or not protocol_lines:
            detail = (stderr or stdout or "worker exited without a result record").strip()
            raise IsolatedHandlerError(
                f"Isolated handler worker failed (exit={process.returncode}): {detail[-2000:]}"
            )
        try:
            response = json.loads(protocol_lines[-1])
        except json.JSONDecodeError as exc:
            raise IsolatedHandlerError("Isolated handler returned malformed result JSON") from exc
        if not isinstance(response, dict) or not response.get("ok"):
            detail = response.get("error", "unspecified isolated handler error") if isinstance(response, dict) else "invalid response"
            raise IsolatedHandlerError(str(detail))
        return response.get("result")

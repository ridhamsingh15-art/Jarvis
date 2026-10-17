"""Write-ahead, restart-safe execution for structured JARVIS missions."""
from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from core.execution_policy import (
    CapabilitySource,
    ExecutionPolicy,
    PolicyContext,
    PolicyVerdict,
)
from core.task import Task, TaskStatus

from .crash_store import CrashSafeMissionStore

_READ_ONLY_ACTIONS = frozenset({
    ("file", "read_file"), ("file", "list_directory"),
    ("file", "list_largest_files"), ("file", "summarize_files"),
})


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stable_key(mission_id: str, index: int, spec: dict[str, Any]) -> str:
    canonical = json.dumps(spec, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(f"{mission_id}\0{index}\0{canonical}".encode()).hexdigest()


def _paths_from_output(output: Any) -> list[str]:
    if isinstance(output, dict):
        paths = output.get("paths", [])
        if isinstance(paths, list):
            return [str(path) for path in paths]
    if isinstance(output, str):
        try:
            data = json.loads(output)
            if isinstance(data, dict):
                return [str(item["path"]) for item in data.get("files", []) if isinstance(item, dict) and item.get("path")]
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
    return []


class CrashSafeMissionRunner:
    """Execute structured tool steps with durable intent and result records.

    ``after_execute`` is a test seam invoked after the real handler returns but
    before result persistence; production callers should leave it unset.
    """

    def __init__(
        self,
        store: CrashSafeMissionStore,
        execution_engine: Any,
        policy: ExecutionPolicy,
        *,
        after_execute: Callable[[str, int, Task], None] | None = None,
    ) -> None:
        self.store = store
        self.execution_engine = execution_engine
        self.policy = policy
        self.after_execute = after_execute

    def run(self, mission_id: str, objective: str, steps: list[str]) -> dict[str, Any]:
        if not steps:
            self.store.create_mission(mission_id, objective)
            reason = "Planner produced no executable steps."
            self.store.set_mission_state(mission_id, "FAILED", reason)
            return self.result(mission_id)
        self.store.create_mission(mission_id, objective)
        mission = self.store.mission(mission_id)
        if mission and mission["state"] in {"COMPLETED", "FAILED"}:
            return self.result(mission_id)

        for index, step_text in enumerate(steps):
            try:
                spec = json.loads(step_text)
                if not isinstance(spec, dict):
                    raise TypeError("step must be a JSON object")
                tool = str(spec["tool"])
                action = str(spec["action"])
                args = spec.get("args", {})
                if not tool or not action or not isinstance(args, dict):
                    raise TypeError("step requires non-empty tool/action and object args")
            except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                self.store.set_mission_state(mission_id, "FAILED", f"Planner produced invalid step {index + 1}: {exc}")
                return self.result(mission_id)

            existing = self.store.step(mission_id, index)
            if existing and existing["status"] == "completed":
                continue
            idempotent = (tool, action) in _READ_ONLY_ACTIONS
            side_effecting = not idempotent
            if existing and existing["status"] == "started" and side_effecting:
                reason = (
                    f"needs_review: step {index + 1} ({tool}.{action}) was started before the previous process "
                    "stopped; the side effect outcome is unknown, so it was not replayed."
                )
                self.store.mark_needs_review(mission_id, index, reason)
                return self.result(mission_id)
            if existing and existing["status"] not in {"started", "completed"}:
                self.store.set_mission_state(mission_id, "FAILED", f"Step {index + 1} is terminal ({existing['status']}); automatic replay is disabled.")
                return self.result(mission_id)

            decision = self.policy.check(PolicyContext(
                tool=tool, action=action, source=CapabilitySource.CORE,
                source_id=f"mission:{mission_id}", user_confirmed=bool(spec.get("user_confirmed", False)),
                request_id=_stable_key(mission_id, index, spec), args=args,
            ))
            idempotency_key = _stable_key(mission_id, index, spec)
            if decision.verdict != PolicyVerdict.ALLOW:
                reason = f"Execution policy {decision.verdict.value} for {tool}.{action}: {decision.reason}"
                record = {
                    "status": "blocked", "stdout": "", "stderr": reason,
                    "normalized_code": 126 if tool == "file" else None,
                    "exit_code": None, "error": reason, "finished_at": _now(), "result": None,
                }
                self.store.begin_step(
                    mission_id=mission_id, step_index=index, tool=tool, action=action, args=args,
                    idempotency_key=idempotency_key, side_effecting=side_effecting, started_at=_now(),
                )
                self.store.finish_step(mission_id, index, record)
                self.store.set_mission_state(mission_id, "FAILED", reason)
                return self.result(mission_id)

            self.store.begin_step(
                mission_id=mission_id, step_index=index, tool=tool, action=action, args=args,
                idempotency_key=idempotency_key, side_effecting=side_effecting, started_at=_now(),
            )
            task = Task(tool=tool, action=f"{tool}.{action}", args=args, max_retries=0)
            try:
                self.execution_engine.execute(task)
                if self.after_execute is not None:
                    self.after_execute(mission_id, index, task)
                output = task.result
                stdout = str(output.get("stdout", "")) if isinstance(output, dict) else str(output if output is not None else "")
                stderr = str(output.get("stderr", "")) if isinstance(output, dict) else ""
                shell_blocked = bool(output.get("blocked", False)) if isinstance(output, dict) else False
                shell_timeout = bool(output.get("timed_out", False)) if isinstance(output, dict) else False
                shell_code = output.get("exit_code") if isinstance(output, dict) and tool == "shell" else None
                normalized_code = None if tool == "shell" else (0 if task.status == TaskStatus.COMPLETED else 1)
                ok = task.status == TaskStatus.COMPLETED and not shell_blocked and not shell_timeout
                if tool == "shell":
                    ok = ok and isinstance(shell_code, int) and shell_code == 0
                status = "completed" if ok else "failed"
                error = "" if ok else (task.error or stderr or ("Shell tool timed out" if shell_timeout else f"Tool result not successful (status={task.status.value}, code={shell_code})"))
                record = {
                    "status": status, "stdout": stdout, "stderr": stderr,
                    "exit_code": shell_code if isinstance(shell_code, int) and not shell_blocked and not shell_timeout else None,
                    "normalized_code": normalized_code, "error": error,
                    "paths": _paths_from_output(output), "result": output, "finished_at": _now(),
                }
                self.store.finish_step(mission_id, index, record)
                if not ok:
                    self.store.set_mission_state(mission_id, "FAILED", f"Step {index + 1} ({tool}.{action}) failed: {error}")
                    return self.result(mission_id)
            except Exception as exc:  # noqa: BLE001 - persist arbitrary tool errors as terminal step failures
                # Process-kill tests terminate the process externally, so this branch is for ordinary exceptions.
                error = f"{type(exc).__name__}: {exc}"
                self.store.finish_step(mission_id, index, {
                    "status": "failed", "stdout": "", "stderr": error,
                    "exit_code": None, "normalized_code": 1 if tool != "shell" else None,
                    "error": error, "finished_at": _now(), "result": None,
                })
                self.store.set_mission_state(mission_id, "FAILED", error)
                return self.result(mission_id)

        self.store.set_mission_state(mission_id, "COMPLETED", "")
        return self.result(mission_id)

    def result(self, mission_id: str) -> dict[str, Any]:
        return {"mission": self.store.mission(mission_id), "steps": self.store.steps(mission_id)}

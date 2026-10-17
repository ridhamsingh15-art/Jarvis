"""Execution-backed mission stepping; unconfigured execution fails closed."""

from __future__ import annotations

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

from .mission import Mission, MissionState


class MissionExecutor:
    """Execute one structured mission step through the real JARVIS executor.

    Mission step strings must be JSON objects containing ``tool``, ``action`` and
    ``args``. A step is only added to ``completed_steps`` after the registered
    action handler returns successfully and the task reaches COMPLETED.
    """

    def __init__(
        self,
        execution_engine: Any | None = None,
        policy: ExecutionPolicy | None = None,
        persist: Callable[[Mission], None] | None = None,
        record_step: Callable[[str, int, dict[str, Any]], None] | None = None,
    ) -> None:
        self.execution_engine = execution_engine
        self.policy = policy
        self.persist = persist
        self.record_step = record_step

    def step(self, mission: Mission) -> None:
        if mission.state != MissionState.RUNNING:
            return
        if self.execution_engine is None or self.policy is None:
            self._fail(mission, "No real execution engine and policy are configured; simulated success is disabled.")
            return

        next_steps = [step for step in mission.steps if step not in mission.completed_steps]
        if not next_steps:
            mission.state = MissionState.COMPLETED
            self._persist(mission)
            return

        step_text = next_steps[0]
        step_index = mission.steps.index(step_text)
        try:
            spec = json.loads(step_text)
            if not isinstance(spec, dict):
                raise TypeError("step must be a JSON object")
            tool = str(spec["tool"])
            action = str(spec["action"])
            args = spec.get("args", {})
            if not isinstance(args, dict):
                raise TypeError("step args must be a JSON object")
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            self._record(mission, step_index, {
                "tool": "", "action": "", "args": {}, "status": "failed",
                "stdout": "", "stderr": "", "exit_code": 2,
                "error": f"Invalid structured mission step: {exc}",
            })
            self._fail(mission, f"Invalid structured mission step {step_index + 1}: {exc}")
            return

        context = PolicyContext(
            tool=tool,
            action=action,
            source=CapabilitySource.CORE,
            source_id=f"mission:{mission.id}",
            user_confirmed=step_text in mission.approved_steps,
            args=args,
        )
        decision = self.policy.check(context)
        if decision.verdict != PolicyVerdict.ALLOW:
            record = {
                "tool": tool, "action": action, "args": args,
                "status": "blocked" if decision.verdict == PolicyVerdict.DENY else "waiting_approval",
                "stdout": "", "stderr": decision.reason, "exit_code": 126,
                "error": decision.reason,
            }
            self._record(mission, step_index, record)
            if decision.verdict == PolicyVerdict.REQUIRE_CONFIRMATION:
                if step_text not in mission.pending_approvals:
                    mission.pending_approvals.append(step_text)
                mission.state = MissionState.WAITING_APPROVAL
                mission.failure_reason = decision.reason
            else:
                self._fail(mission, f"Execution policy denied {tool}.{action}: {decision.reason}")
            self._persist(mission)
            return

        started_at = datetime.now(timezone.utc).isoformat()
        running_record = {
            "tool": tool, "action": action, "args": args, "status": "running",
            "stdout": "", "stderr": "", "exit_code": None, "error": "",
            "started_at": started_at,
        }
        self._record(mission, step_index, running_record)
        self._persist(mission)

        task = Task(tool=tool, action=f"{tool}.{action}", args=args, max_retries=0)
        try:
            self.execution_engine.execute(task)
            if task.status != TaskStatus.COMPLETED:
                error = task.error or f"Executor returned {task.status.value} without a result"
                result_record = {
                    **running_record, "status": "failed", "stdout": "",
                    "stderr": error, "exit_code": 1, "error": error,
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                }
                self._record(mission, step_index, result_record)
                self._fail(mission, f"Step {step_index + 1} ({tool}.{action}) failed: {error}")
                return

            output = task.result
            if isinstance(output, dict):
                stdout = str(output.get("stdout", output.get("output", output)))
                stderr = str(output.get("stderr", ""))
                exit_code = int(output.get("exit_code", 0))
                paths = output.get("paths", [])
            else:
                stdout = str(output if output is not None else "")
                stderr = ""
                exit_code = 0
                paths = []
                try:
                    parsed_output = json.loads(stdout)
                    if isinstance(parsed_output, dict):
                        paths = [str(item["path"]) for item in parsed_output.get("files", []) if isinstance(item, dict) and item.get("path")]
                except (json.JSONDecodeError, TypeError, ValueError):
                    pass
            result_record = {
                **running_record, "status": "completed" if exit_code == 0 else "failed",
                "stdout": stdout, "stderr": stderr, "exit_code": exit_code,
                "error": "" if exit_code == 0 else f"Tool returned exit code {exit_code}",
                "paths": paths, "result": output,
                "finished_at": datetime.now(timezone.utc).isoformat(),
            }
            self._record(mission, step_index, result_record)
            if exit_code != 0:
                self._fail(mission, f"Step {step_index + 1} ({tool}.{action}) returned exit code {exit_code}")
                return
            mission.completed_steps.append(step_text)
            mission.step_results = [r for r in mission.step_results if r.get("step_index") != step_index]
            mission.step_results.append({"step_index": step_index, **result_record})
            mission.failure_reason = ""
            if len(mission.completed_steps) == len(mission.steps):
                mission.state = MissionState.COMPLETED
            self._persist(mission)
        except Exception as exc:  # noqa: BLE001 - persist arbitrary tool failures as terminal step results
            error = f"{type(exc).__name__}: {exc}"
            result_record = {
                **running_record, "status": "failed", "stdout": "", "stderr": error,
                "exit_code": 1, "error": error,
                "finished_at": datetime.now(timezone.utc).isoformat(),
            }
            self._record(mission, step_index, result_record)
            self._fail(mission, f"Step {step_index + 1} ({tool}.{action}) failed: {error}")

    def _record(self, mission: Mission, step_index: int, record: dict[str, Any]) -> None:
        if self.record_step is not None:
            self.record_step(mission.id, step_index, record)
        mission.step_results = [r for r in mission.step_results if r.get("step_index") != step_index]
        mission.step_results.append({"step_index": step_index, **record})

    def _fail(self, mission: Mission, reason: str) -> None:
        mission.state = MissionState.FAILED
        mission.failure_reason = reason
        self._persist(mission)

    def _persist(self, mission: Mission) -> None:
        if self.persist is not None:
            self.persist(mission)

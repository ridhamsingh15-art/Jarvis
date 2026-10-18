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

from .mission import Mission, MissionState, normalize_step_indexes


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

        from .crash_safe import _READ_ONLY_ACTIONS

        completed_indexes = {
            record.get("step_index") for record in mission.step_results
            if record.get("status") == "completed" and isinstance(record.get("step_index"), int)
        }
        # The legacy GUI/store path persists a running record before invoking a
        # handler. After a process crash, never replay a side-effecting step whose
        # prior invocation may have crossed the side-effect boundary.
        for previous in mission.step_results:
            previous_index = previous.get("step_index")
            if (
                previous.get("status") not in {"running", "needs_review"}
                or not isinstance(previous_index, int)
                or previous_index in completed_indexes
                or not 0 <= previous_index < len(mission.steps)
            ):
                continue
            previous_tool = str(previous.get("tool", ""))
            previous_action = str(previous.get("action", ""))
            if (previous_tool, previous_action) in _READ_ONLY_ACTIONS:
                continue
            error = (
                "OUTCOME UNKNOWN: a previous process left this side-effecting step "
                "running or awaiting review. Inspect external state and explicitly "
                "reconcile it before any retry."
            )
            record = {
                **previous,
                "status": "needs_review",
                "error": error,
                "stderr": error,
                "verification": {"status": "not_run", "method": "interrupted legacy step requires operator reconciliation"},
                "finished_at": datetime.now(timezone.utc).isoformat(),
            }
            self._record(mission, previous_index, record)
            self._fail(mission, error)
            return
        next_indexes = [index for index in range(len(mission.steps)) if index not in completed_indexes]
        if not next_indexes:
            mission.state = MissionState.COMPLETED
            self._persist(mission)
            return

        step_index = next_indexes[0]
        step_text = mission.steps[step_index]
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

        # Revalidate occurrence indexes at the execution boundary because a Mission
        # may be constructed directly or mutated after deserialization.
        approved_step_indexes = normalize_step_indexes(
            mission.approved_step_indexes, len(mission.steps)
        )
        context = PolicyContext(
            tool=tool,
            action=action,
            source=CapabilitySource.CORE,
            source_id=f"mission:{mission.id}",
            # Legacy approvals identify steps by serialized text, not occurrence.
            # Duplicate text is ambiguous, so never let one approval authorize both.
            user_confirmed=(
                step_index in approved_step_indexes
                or (
                    step_text in mission.approved_steps
                    and mission.steps.count(step_text) == 1
                )
            ),
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
                if step_index not in mission.pending_approval_indexes:
                    mission.pending_approval_indexes.append(step_index)
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
        from .crash_safe import _capture_append_line_baseline, _windows_process_images
        baseline_process_images = (
            _windows_process_images() if tool == "windows" and action == "open_app" else None
        )
        baseline_file_size = (
            _capture_append_line_baseline(args) if tool == "file" and action == "append_line" else None
        )
        try:
            self.execution_engine.execute(task)
            if task.status != TaskStatus.COMPLETED:
                error = task.error or f"Executor returned {task.status.value} without a result"
                from .crash_safe import _READ_ONLY_ACTIONS
                uncertain_side_effect = (tool, action) not in _READ_ONLY_ACTIONS
                if uncertain_side_effect:
                    error = (
                        "OUTCOME UNKNOWN: isolated handler did not return a verified result; "
                        "do not retry until external state is reconciled. " + error
                    )
                result_record = {
                    **running_record,
                    "status": "needs_review" if uncertain_side_effect else "failed",
                    "stdout": "", "stderr": error, "exit_code": 1, "error": error,
                    "verification": {"status": "not_run", "method": "handler did not return a verifiable result"},
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                }
                self._record(mission, step_index, result_record)
                self._fail(mission, f"Step {step_index + 1} ({tool}.{action}) failed: {error}")
                return

            output = task.result
            if isinstance(output, dict):
                stdout = str(output.get("stdout", output.get("output", output)))
                stderr = str(output.get("stderr", ""))
                raw_exit_code = output.get("exit_code", 1)
                # A malformed or absent exit code is not evidence of success.
                exit_code = raw_exit_code if isinstance(raw_exit_code, int) and not isinstance(raw_exit_code, bool) else 1
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
            from .crash_safe import (
                _verify_action_outcome,
                _verify_file_mutation_outcome,
            )
            verification = _verify_action_outcome(
                tool, action, args, output, baseline_process_images=baseline_process_images,
            )
            if tool == "file" and action in {
                "create_file", "write_file", "append_line", "patch_file", "edit_file",
                "create_folder", "rename", "move", "copy", "delete",
            }:
                verification = _verify_file_mutation_outcome(action, args, baseline_file_size)
            verified = verification.get("status") == "verified"
            if exit_code == 0 and not verified:
                error = str(
                    verification.get("error") or verification.get("limitation")
                    or f"Independent outcome verification did not establish success (status={verification.get('status', 'missing')})."
                )
                result_record = {
                    **running_record, "status": "needs_review" if tool != "file" or action not in {
                        "read_file", "list_largest_files", "summarize_files", "directory_file_stats",
                        "extension_counts", "list_directory_details", "ensure_text_files",
                    } else "failed",
                    "stdout": stdout, "stderr": stderr, "exit_code": exit_code,
                    "error": error, "paths": paths, "result": output,
                    "verification": verification,
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                }
                self._record(mission, step_index, result_record)
                self._fail(mission, f"Step {step_index + 1} ({tool}.{action}) was not independently verified: {error}")
                return
            result_record = {
                **running_record, "status": "completed" if exit_code == 0 and verified else "failed",
                "stdout": stdout, "stderr": stderr, "exit_code": exit_code,
                "error": "" if exit_code == 0 else f"Tool returned exit code {exit_code}",
                "paths": paths, "result": output, "verification": verification,
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
            completed_step_indexes = {
                item.get("step_index") for item in mission.step_results
                if item.get("status") == "completed"
                and isinstance(item.get("step_index"), int)
            }
            if all(index in completed_step_indexes for index in range(len(mission.steps))):
                mission.state = MissionState.COMPLETED
            self._persist(mission)
        except Exception as exc:  # noqa: BLE001 - preserve uncertainty after side-effect boundary
            from .crash_safe import _READ_ONLY_ACTIONS
            uncertain_side_effect = (tool, action) not in _READ_ONLY_ACTIONS
            error = f"{type(exc).__name__}: {exc}"
            if uncertain_side_effect:
                error = (
                    "OUTCOME UNKNOWN: handler raised after invocation; do not retry until "
                    "external state is reconciled. " + error
                )
            result_record = {
                **running_record,
                "status": "needs_review" if uncertain_side_effect else "failed",
                "stdout": "", "stderr": error,
                "exit_code": 1, "error": error,
                "verification": {"status": "not_run", "method": "handler raised before independent verification"},
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

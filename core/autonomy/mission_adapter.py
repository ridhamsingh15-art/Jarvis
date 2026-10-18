"""Bridge autonomous goals to JARVIS's policy-gated crash-safe mission runner.

Only objectives understood by the explicit mission planner are accepted. This
adapter never interprets free-form step text as a command.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
from typing import Any, ClassVar

from core.models.primitives import Identifier

from .exceptions import GoalExecutionError, GoalInterventionRequired
from .interfaces import IGoalPlanner
from .models import Goal, GoalPlan, GoalStep
from .step_executor import IGoalStepExecutor


class ExecutionBackedGoalPlanner(IGoalPlanner):
    """Translate objectives into validated, policy-gated tool steps."""

    _RECOVERABLE_ACTIONS: ClassVar[frozenset[tuple[str, str]]] = frozenset({
        ("file", "list_directory"), ("file", "read_file"),
        ("file", "list_largest_files"), ("file", "summarize_files"),
        ("file", "directory_file_stats"), ("file", "extension_counts"),
        ("file", "list_directory_details"), ("file", "ensure_text_files"),
    })
    _REPLAN_SAFE_ACTIONS: ClassVar[frozenset[tuple[str, str]]] = frozenset({
        ("file", "list_directory"), ("file", "read_file"),
        ("file", "list_largest_files"), ("file", "summarize_files"),
        ("file", "directory_file_stats"), ("file", "extension_counts"),
        ("file", "list_directory_details"),
    })

    def __init__(self, tool_registry: Any | None = None) -> None:
        # The same explicit registry is shared with execution; model-visible tools
        # must never exceed the capabilities the crash-safe runner can invoke.
        self._tool_registry = tool_registry

    def create_plan(self, goal: Goal) -> GoalPlan:
        from mission_control.objective_planner import build_adaptive_objective_plan

        encoded_steps = build_adaptive_objective_plan(
            goal.description, tool_registry=self._tool_registry,
        )
        return self._make_goal_plan(goal, encoded_steps, f"autonomy-{goal.id.value}")

    def replan_after_failure(
        self, goal: Goal, previous_plan: GoalPlan, failure_reason: str
    ) -> GoalPlan | None:
        """Try one model-driven alternative only when every previous action is replay-safe."""
        lowered = failure_reason.casefold()
        if any(marker in lowered for marker in ("execution policy", "needs_review", "unknown side-effect", "side effect outcome is unknown", "blocked", "approval")):
            return None
        encoded_steps = previous_plan.steps[0].context.get("mission_steps", []) if previous_plan.steps else []
        if not isinstance(encoded_steps, list) or not encoded_steps:
            return None
        parsed_previous = [json.loads(item) for item in encoded_steps]
        if any((item.get("tool"), item.get("action")) not in self._RECOVERABLE_ACTIONS for item in parsed_previous):
            return None

        from config.config import load_config
        from core.llm import LLMClient
        from mission_control.objective_planner import _build_llm_objective_plan

        replacement = _build_llm_objective_plan(
            goal.description,
            LLMClient(load_config()),
            recovery_context={
                "failed_plan": [
                    {"tool": item.get("tool"), "action": item.get("action"), "args": item.get("args", {})}
                    for item in parsed_previous
                ],
                "failure_reason": failure_reason[:1000],
                "previous_verified_evidence": goal.metadata.get("recovery_evidence", [])[:8],
            },
            tool_registry=self._tool_registry,
        )
        def action_signature(items: list[str]) -> list[tuple[str, str, dict[str, Any]]]:
            return [
                (str(item.get("tool", "")), str(item.get("action", "")), item.get("args", {}))
                for item in (json.loads(encoded) for encoded in items)
            ]

        if action_signature(replacement) == action_signature(encoded_steps):
            return None
        return self._make_goal_plan(goal, replacement, f"autonomy-{goal.id.value}-replan1")

    @staticmethod
    def _make_goal_plan(goal: Goal, encoded_steps: list[str], mission_id: str) -> GoalPlan:
        parsed_steps = [json.loads(encoded) for encoded in encoded_steps]
        if not all(isinstance(spec, dict) for spec in parsed_steps):
            raise GoalExecutionError("Objective planner returned a non-object step.")

        step_ids: dict[str, Identifier] = {}
        for index, spec in enumerate(parsed_steps, start=1):
            raw_id = spec.get("id", f"step_{index}")
            if not isinstance(raw_id, str) or not raw_id or raw_id in step_ids:
                raise GoalExecutionError("Objective planner returned a missing or duplicate step id.")
            step_ids[raw_id] = Identifier(f"{goal.id.value}_step_{index}")

        steps: list[GoalStep] = []
        previous: Identifier | None = None
        for index, spec in enumerate(parsed_steps, start=1):
            tool, action, args = spec.get("tool"), spec.get("action"), spec.get("args", {})
            if not isinstance(tool, str) or not tool or not isinstance(action, str) or not action:
                raise GoalExecutionError("Objective planner returned a step without tool/action.")
            if not isinstance(args, dict):
                raise GoalExecutionError("Objective planner returned non-object step arguments.")
            raw_id = spec.get("id", f"step_{index}")
            step_id = step_ids[raw_id]
            declared_dependencies = spec.get("depends_on")
            if declared_dependencies is None:
                dependency_ids = [previous] if previous is not None else []
            else:
                if not isinstance(declared_dependencies, list) or any(
                    not isinstance(item, str) or item not in step_ids for item in declared_dependencies
                ):
                    raise GoalExecutionError("Objective planner returned invalid step dependencies.")
                dependency_ids = [step_ids[item] for item in declared_dependencies]
                if previous is not None and previous not in dependency_ids:
                    dependency_ids.append(previous)
            step_context = {
                "tool": tool, "action": action, "args": args,
                "mission_steps": encoded_steps, "plan_step_index": index - 1,
                "mission_id": mission_id,
            }
            expected_outcome = spec.get("expected_outcome")
            if isinstance(expected_outcome, str) and expected_outcome:
                step_context["expected_outcome"] = expected_outcome
            steps.append(GoalStep(
                id=step_id, description=f"Execute registered action {tool}.{action}",
                dependencies=dependency_ids, context=step_context,
            ))
            previous = step_id
        if not steps:
            raise GoalExecutionError("Objective planner produced no executable steps.")
        return GoalPlan(goal_id=goal.id, steps=steps)


class CrashSafeGoalStepExecutor(IGoalStepExecutor):
    """Execute a structured step using the existing policy-gated WAL runner."""

    _REPLAN_SAFE_ACTIONS: ClassVar[frozenset[tuple[str, str]]] = frozenset({
        ("file", "list_directory"), ("file", "read_file"),
        ("file", "list_largest_files"), ("file", "summarize_files"),
        ("file", "directory_file_stats"), ("file", "extension_counts"),
        ("file", "list_directory_details"),
    })

    def __init__(self, tool_registry: Any | None = None) -> None:
        self._tool_registry = tool_registry

    async def execute_plan(self, goal: Goal, plan: GoalPlan) -> list[dict[str, Any]]:
        """Run the persisted mission once and return one result per planned step.

        The mission runner already owns dependency resolution, WAL persistence,
        recovery and postcondition verification. Calling it once per GoalStep
        would replay the whole mission repeatedly, so the goal manager uses this
        batch contract when available.
        """
        if not plan.steps:
            raise GoalExecutionError("Cannot execute an empty autonomous plan.")
        first_context = plan.steps[0].context
        mission_steps = first_context.get("mission_steps")
        mission_id = first_context.get("mission_id")
        if (
            not isinstance(mission_steps, list)
            or not mission_steps
            or not all(isinstance(item, str) for item in mission_steps)
            or len(mission_steps) != len(plan.steps)
            or not isinstance(mission_id, str)
            or not mission_id
        ):
            raise GoalExecutionError("Autonomous plan has no valid persisted mission contract.")

        for index, step in enumerate(plan.steps):
            context = step.context
            if (
                context.get("mission_steps") != mission_steps
                or context.get("mission_id") != mission_id
                or context.get("plan_step_index") != index
            ):
                raise GoalExecutionError("Autonomous plan contains inconsistent mission step metadata.")

        goal.metadata["batch_execution"] = True
        goal.metadata.pop("safe_replan_allowed", None)
        try:
            from mission_control.crash_cli import execute_objective
            result = await asyncio.to_thread(
                execute_objective, goal.description, mission_id=mission_id,
                steps=mission_steps, tool_registry=self._tool_registry,
            )
        except Exception as exc:
            raise GoalExecutionError(
                f"Real mission execution failed: {type(exc).__name__}: {exc}"
            ) from exc

        mission = result.get("mission") if isinstance(result, dict) else None
        rows = result.get("steps", []) if isinstance(result, dict) else []
        state = mission.get("state") if isinstance(mission, dict) else None
        if not isinstance(rows, list):
            rows = []

        verified_evidence: list[dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            verification = row.get("verification", {})
            if row.get("status") != "completed" or not isinstance(verification, dict) or verification.get("status") != "verified":
                continue
            output = row.get("result")
            if row.get("action") == "read_file":
                raw = output if isinstance(output, str) else json.dumps(output, ensure_ascii=False, default=str)
                output = {"sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(), "character_count": len(raw)}
            elif isinstance(output, str):
                try:
                    output = json.loads(output)
                except json.JSONDecodeError:
                    output = output[:1500]
            verified_evidence.append({
                "step_index": row.get("step_index"),
                "tool": row.get("tool"),
                "action": row.get("action"),
                "args": row.get("args", {}),
                "verification": verification,
                "output": output,
            })

        mission_verification = mission.get("verification_status", "not_verified") if isinstance(mission, dict) else "not_verified"
        if state in {"WAITING_APPROVAL", "NEEDS_REVIEW", "RECOVERY_REQUIRED"}:
            if verified_evidence:
                goal.metadata["recovery_evidence"] = verified_evidence[:8]
            if any(isinstance(row, dict) and row.get("status") == "completed" for row in rows):
                goal.metadata["batch_partial_execution"] = True
            reason = mission.get("failure_reason", "Operator action is required.") if isinstance(mission, dict) else "Operator action is required."
            raise GoalInterventionRequired(
                f"Mission {mission_id} requires operator intervention ({state}): {reason}"
            )

        rows_complete = len(rows) == len(plan.steps) and all(
            isinstance(row, dict) and row.get("status") == "completed"
            for row in rows
        )
        steps_verified = rows_complete and all(
            isinstance(row.get("verification"), dict)
            and row["verification"].get("status") == "verified"
            for row in rows
        )
        if state != "COMPLETED" or not rows_complete or mission_verification != "verified" or not steps_verified:
            if verified_evidence:
                goal.metadata["recovery_evidence"] = verified_evidence[:8]

            # Permit a bounded replan only when every prior step completed with
            # independent verification and was read-only, and the failing action
            # is itself read-only. Unknown/side-effecting outcomes require review.
            failed_rows = [
                row for row in rows
                if isinstance(row, dict) and row.get("status") == "failed"
            ]
            safe_replan = False
            if state == "FAILED" and len(failed_rows) == 1:
                failed_row = failed_rows[0]
                failed_index = failed_row.get("step_index")
                prior_rows = [
                    row for row in rows
                    if isinstance(row, dict) and isinstance(failed_index, int)
                    and row.get("step_index", failed_index) < failed_index
                ]
                prior_verified_read_only = all(
                    row.get("status") == "completed"
                    and isinstance(row.get("verification"), dict)
                    and row["verification"].get("status") == "verified"
                    and (row.get("tool"), row.get("action")) in self._REPLAN_SAFE_ACTIONS
                    for row in prior_rows
                )
                safe_replan = (
                    isinstance(failed_index, int)
                    and (failed_row.get("tool"), failed_row.get("action")) in self._REPLAN_SAFE_ACTIONS
                    and not failed_row.get("side_effecting", False)
                    and prior_verified_read_only
                    and len(prior_rows) == failed_index
                )
            if safe_replan:
                goal.metadata["safe_replan_allowed"] = True
                goal.metadata["batch_partial_execution"] = False
                goal.metadata["recovery_evidence"] = verified_evidence[:8]
            elif any(isinstance(row, dict) and row.get("status") == "completed" for row in rows):
                # If the prior work cannot be proven safe for replanning, prevent
                # a fresh plan from repeating even apparently read-only operations.
                goal.metadata["batch_partial_execution"] = True

            elif rows and all(
                isinstance(row, dict) and row.get("status") in {"blocked", "pending_approval"}
                for row in rows
            ):
                # The policy ledger proves that no action ran. A denied request is
                # a known failure, not an unknown side-effect outcome.
                goal.metadata.pop("in_flight_batch", None)
                goal.metadata.pop("execution_state_untrusted", None)

            reason = mission.get("failure_reason", "Mission did not return independently verified results for every step.") if isinstance(mission, dict) else "Invalid mission result."
            raise GoalExecutionError(
                f"Real mission execution ended in {state or 'UNKNOWN'} with verification={mission_verification}: {reason}"
            )

        results: list[dict[str, Any]] = []
        for index, (step, row) in enumerate(zip(plan.steps, rows, strict=True)):
            if row.get("tool") != step.context.get("tool") or row.get("action") != step.context.get("action"):
                raise GoalExecutionError(f"Mission result does not match planned step {index + 1}.")
            output = row.get("result")
            rendered = json.dumps(output, ensure_ascii=False, default=str) if output is not None else ""
            results.append({
                "mission_id": mission_id,
                "state": state,
                "tool": row.get("tool"),
                "action": row.get("action"),
                "status": row.get("status"),
                "verification_status": row.get("verification", {}).get("status", "not_verified"),
                "step_verification": row.get("verification", {}),
                "output": rendered[:50000],
                "paths": row.get("paths", []),
            })
        return results

    async def execute(self, goal: Goal, step: GoalStep) -> dict[str, Any]:
        tool = step.context.get("tool")
        action = step.context.get("action")
        args = step.context.get("args", {})
        if not isinstance(tool, str) or not tool or not isinstance(action, str) or not action:
            raise GoalExecutionError(f"Step {step.id.value} has no valid structured tool/action.")
        if not isinstance(args, dict):
            raise GoalExecutionError(f"Step {step.id.value} has invalid structured arguments.")

        mission_steps = step.context.get("mission_steps")
        step_index = step.context.get("plan_step_index")
        if (
            not isinstance(mission_steps, list)
            or not mission_steps
            or not all(isinstance(item, str) for item in mission_steps)
            or not isinstance(step_index, int)
            or isinstance(step_index, bool)
            or not 0 <= step_index < len(mission_steps)
        ):
            raise GoalExecutionError(f"Step {step.id.value} has no valid persisted mission plan.")
        if len(mission_steps) != 1 or step_index != 0:
            raise GoalExecutionError(
                "Multi-step crash-safe missions must use execute_plan(); refusing to replay the whole mission per step."
            )
        mission_id = step.context.get("mission_id", f"autonomy-{goal.id.value}")
        if not isinstance(mission_id, str) or not mission_id:
            raise GoalExecutionError(f"Step {step.id.value} has an invalid mission id.")
        try:
            from mission_control.crash_cli import execute_objective
            result = await asyncio.to_thread(
                execute_objective, goal.description, mission_id=mission_id,
                steps=mission_steps, tool_registry=self._tool_registry,
            )
        except Exception as exc:
            raise GoalExecutionError(
                f"Real execution failed for {tool}.{action}: {type(exc).__name__}: {exc}"
            ) from exc

        mission = result.get("mission") if isinstance(result, dict) else None
        state = mission.get("state") if isinstance(mission, dict) else None
        if state != "COMPLETED":
            reason = mission.get("failure_reason", "No successful mission result was returned.") if isinstance(mission, dict) else "Invalid mission result returned."
            # Preserve only independently verified evidence from completed steps. Raw file
            # contents are never copied into recovery context; retain a digest instead.
            evidence = []
            for prior in result.get("steps", []) if isinstance(result, dict) else []:
                if not isinstance(prior, dict) or prior.get("status") != "completed" or prior.get("verification", {}).get("status") != "verified":
                    continue
                prior_output = prior.get("result")
                if prior.get("action") == "read_file":
                    raw = prior_output if isinstance(prior_output, str) else json.dumps(prior_output, ensure_ascii=False, default=str)
                    prior_output = {"sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(), "character_count": len(raw)}
                elif isinstance(prior_output, str):
                    try:
                        prior_output = json.loads(prior_output)
                    except json.JSONDecodeError:
                        prior_output = prior_output[:1500]
                evidence.append({
                    "step_index": prior.get("step_index"), "tool": prior.get("tool"),
                    "action": prior.get("action"), "args": prior.get("args", {}),
                    "verification": prior.get("verification"), "output": prior_output,
                })
            goal.metadata["recovery_evidence"] = evidence[:8]
            raise GoalExecutionError(f"Real execution failed for {tool}.{action}: {reason}")

        rows = result.get("steps", [])
        row = rows[step_index] if isinstance(rows, list) and step_index < len(rows) else {}
        if not isinstance(row, dict) or row.get("status") != "completed":
            raise GoalExecutionError(f"Real execution did not verify completion of planned step {step_index + 1}.")
        output = row.get("result")
        rendered = json.dumps(output, ensure_ascii=False, default=str) if output is not None else ""
        return {
            "mission_id": mission_id,
            "state": state,
            "tool": tool,
            "action": action,
            "status": row.get("status", "completed") if isinstance(row, dict) else "completed",
            "verification_status": mission.get("verification_status", "not_verified"),
            "step_verification": row.get("verification", {}) if isinstance(row, dict) else {},
            "output": rendered[:50000],
            "paths": row.get("paths", []) if isinstance(row, dict) else [],
        }

"""
Tool Feedback Loop — Phase A implementation.

Provides a bounded retry loop for TOOL-path execution:

  LLM → tool call → result → evaluate → retry/continue/succeed/fail

STRICT LIMITS:
  - MAX_TOOL_ITERATIONS = 3 (configurable, enforced in code — not by LLM)
  - Loop detection: identical (tool, action, args) cannot repeat
  - Iteration count tracked per request_id for telemetry

Architecture::

    ToolFeedbackLoop.run(request_id, user_input, initial_tasks)
        ├── iteration 1: execute tasks
        │     ├── all succeed → return results
        │     ├── some failed → LLM retry call → new tasks
        │     └── max iterations → return with failure explanation
        └── ...

The loop NEVER calls ExecutiveBrain or ReasoningLoop.
It uses only CognitiveManager.process_fast() for correction hints.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable

from core.task import Task, TaskStatus

if TYPE_CHECKING:
    from core.cognition.manager import CognitiveManager

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MAX_TOOL_ITERATIONS: int = 3


# ---------------------------------------------------------------------------
# Iteration record (telemetry)
# ---------------------------------------------------------------------------


@dataclass
class ToolIteration:
    iteration: int
    tool_name: str
    action: str
    success: bool
    latency_ms: float
    reason: str = ""

    def as_log_dict(self) -> dict:
        return {
            "iteration": self.iteration,
            "tool": self.tool_name,
            "action": self.action,
            "success": self.success,
            "latency_ms": round(self.latency_ms, 1),
            "reason": self.reason,
        }


@dataclass
class ToolLoopResult:
    """Final outcome of a ToolFeedbackLoop.run() call."""
    tasks: list[Task]
    iterations_used: int
    succeeded: bool
    iterations: list[ToolIteration] = field(default_factory=list)
    loop_detected: bool = False
    limit_reached: bool = False


# ---------------------------------------------------------------------------
# Fingerprint helper
# ---------------------------------------------------------------------------


def _task_fingerprint(task: Task) -> str:
    """Stable hash of (tool, action, args) to detect repeated identical calls."""
    payload = json.dumps(
        {"tool": task.tool, "action": task.action, "args": task.args},
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# ToolFeedbackLoop
# ---------------------------------------------------------------------------


class ToolFeedbackLoop:
    """
    Executes tool tasks with bounded retry on failure.

    Parameters
    ----------
    execute_fn:
        Callable[[Task], Task] — the existing Agent._process_task function.
        Keeps the loop decoupled from Agent internals.
    cognitive_manager:
        Optional CognitiveManager used for generating correction prompts on
        failure. If None, loop retries without LLM guidance (raw retry).
    max_iterations:
        Hard cap, enforced in code. Default MAX_TOOL_ITERATIONS = 3.
    """

    def __init__(
        self,
        execute_fn: Callable[[Task], Task],
        cognitive_manager: "CognitiveManager | None" = None,
        max_iterations: int = MAX_TOOL_ITERATIONS,
    ) -> None:
        if max_iterations < 1:
            raise ValueError(f"max_iterations must be >= 1, got {max_iterations}")
        self._execute = execute_fn
        self._cognitive_manager = cognitive_manager
        self._max_iterations = max_iterations

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def run(
        self,
        request_id: str,
        user_input: str,
        initial_tasks: list[Task],
    ) -> ToolLoopResult:
        """
        Execute tasks with up to max_iterations retry attempts.

        Returns:
            ToolLoopResult with final tasks, iteration log, and outcome flags.
        """
        seen_fingerprints: set[str] = set()
        iterations_log: list[ToolIteration] = []
        current_tasks = initial_tasks
        loop_detected = False

        for iteration in range(1, self._max_iterations + 1):
            logger.info(
                "[TOOL_LOOP] request_id=%s iteration=%d/%d tasks=%d",
                request_id, iteration, self._max_iterations, len(current_tasks),
            )

            executed: list[Task] = []
            all_succeeded = True

            for task in current_tasks:
                if task.tool == "system":
                    # system tasks pass through unchanged
                    if task.status in (TaskStatus.PENDING, TaskStatus.RETRYING):
                        task.start()
                    raw_msg = (
                        task.args.get("message")
                        or task.args.get("content")
                        or task.args.get("response")
                        or task.args.get("text")
                        or ""
                    )
                    task.complete(str(raw_msg))
                    executed.append(task)
                    continue

                # Loop detection
                fp = _task_fingerprint(task)
                if fp in seen_fingerprints:
                    logger.warning(
                        "[TOOL_LOOP] Loop detected: identical task '%s.%s' repeated. Stopping.",
                        task.tool, task.action,
                    )
                    loop_detected = True
                    if task.status in (TaskStatus.PENDING, TaskStatus.RETRYING):
                        task.start()
                    task.fail("Loop detected: identical tool call repeated.")
                    executed.append(task)
                    all_succeeded = False
                    continue
                seen_fingerprints.add(fp)

                # Execute
                t0 = time.perf_counter()
                result = self._execute(task)
                latency_ms = (time.perf_counter() - t0) * 1000
                executed.append(result)

                success = result.status == TaskStatus.COMPLETED
                if not success:
                    all_succeeded = False

                iterations_log.append(ToolIteration(
                    iteration=iteration,
                    tool_name=task.tool,
                    action=task.action,
                    success=success,
                    latency_ms=latency_ms,
                    reason=result.error or "",
                ))

                logger.info(
                    "[TOOL_LOOP] request_id=%s iter=%d tool=%s.%s success=%s latency=%.1fms",
                    request_id, iteration, task.tool, task.action, success, latency_ms,
                )

            if loop_detected:
                return ToolLoopResult(
                    tasks=executed,
                    iterations_used=iteration,
                    succeeded=False,
                    iterations=iterations_log,
                    loop_detected=True,
                )

            if all_succeeded:
                logger.info(
                    "[TOOL_LOOP] request_id=%s completed successfully on iteration %d",
                    request_id, iteration,
                )
                from core.execution_summary import ExecutionSummary
                summary = ExecutionSummary.from_tasks(executed)
                for t in executed:
                    if t.tool == "system" and t.action == "respond":
                        t.result = summary.ground_response(str(t.result or t.args.get("message", "")))
                return ToolLoopResult(
                    tasks=executed,
                    iterations_used=iteration,
                    succeeded=True,
                    iterations=iterations_log,
                )

            # Failed tasks — attempt retry if iterations remain
            if iteration >= self._max_iterations:
                logger.warning(
                    "[TOOL_LOOP] request_id=%s reached max iterations (%d). Returning failure.",
                    request_id, self._max_iterations,
                )
                # Add user-visible failure explanation task
                failed_tools = [
                    f"{t.tool}.{t.action}" for t in executed
                    if t.status == TaskStatus.FAILED and t.tool != "system"
                ]
                explain_msg = (
                    f"I tried {iteration} time(s) but could not complete: "
                    + ", ".join(failed_tools or ["the requested action"])
                    + ". Please check if the required application or resource is available."
                )
                executed.append(Task(tool="system", action="respond", args={"message": explain_msg}))
                return ToolLoopResult(
                    tasks=executed,
                    iterations_used=iteration,
                    succeeded=False,
                    iterations=iterations_log,
                    limit_reached=True,
                )

            # Build retry tasks from failed ones
            current_tasks = self._build_retry_tasks(
                user_input=user_input,
                failed_tasks=[t for t in executed if t.status == TaskStatus.FAILED and t.tool != "system"],
                iteration=iteration,
            )
            if not current_tasks:
                # Nothing to retry
                return ToolLoopResult(
                    tasks=executed,
                    iterations_used=iteration,
                    succeeded=False,
                    iterations=iterations_log,
                )

        # Should never reach here, but be safe
        return ToolLoopResult(
            tasks=current_tasks,
            iterations_used=self._max_iterations,
            succeeded=False,
            iterations=iterations_log,
            limit_reached=True,
        )

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _build_retry_tasks(
        self,
        user_input: str,
        failed_tasks: list[Task],
        iteration: int,
    ) -> list[Task]:
        """
        Build retry tasks for failed ones.

        If CognitiveManager is available, ask it for a corrected tool call.
        Otherwise, re-queue the same tasks (raw retry without LLM guidance).
        """
        if not failed_tasks:
            return []

        logger.info(
            "[TOOL_LOOP] Building retry tasks for %d failed task(s) (iteration %d)",
            len(failed_tasks), iteration,
        )

        if self._cognitive_manager is None:
            # Controlled raw retry: transition via task.retry() respecting retry limits
            retry_tasks = []
            for t in failed_tasks:
                if t.retry_count < t.max_retries:
                    t.retry()
                    retry_tasks.append(t)
                else:
                    logger.warning(
                        "[TOOL_LOOP] Task %s.%s reached max retries (%d)",
                        t.tool, t.action, t.max_retries,
                    )
            return retry_tasks

        # LLM-guided retry: ask CognitiveManager for a corrected call
        failure_summary = "; ".join(
            f"{t.tool}.{t.action} failed: {t.error}" for t in failed_tasks
        )
        correction_prompt = (
            f"The following tool call(s) failed on attempt {iteration}: {failure_summary}. "
            f"Original user request: '{user_input}'. "
            "Please suggest a corrected tool call or acknowledge failure."
        )
        try:
            response = self._cognitive_manager.process_fast(correction_prompt, intent="tool")
            if response.type == "ACTION" and response.tool and response.action:
                logger.info(
                    "[TOOL_LOOP] LLM correction suggested: %s.%s",
                    response.tool, response.action,
                )
                return [
                    Task(tool="system", action="respond", args={"message": response.message}),
                    Task(tool=response.tool, action=response.action, args=response.parameters or {}),
                ]
            # LLM gave a non-ACTION response — treat as graceful failure acknowledgement
            return [Task(tool="system", action="respond", args={"message": response.message})]
        except Exception as exc:  # noqa: BLE001
            logger.warning("[TOOL_LOOP] LLM correction failed: %s. Raw retry.", exc)
            retry_tasks = []
            for t in failed_tasks:
                if t.retry_count < t.max_retries:
                    t.retry()
                    retry_tasks.append(t)
            return retry_tasks

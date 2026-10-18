"""
Executor — runs validated Task objects against registered tools.

Takes a Task in PENDING state, transitions it through RUNNING
to COMPLETED or FAILED. Looks up the tool via the Registry and
delegates execution. Never parses JSON, never talks to the LLM.
"""

import logging

from core.action_safety import (
    is_known_pre_side_effect_failure,
    is_known_read_only_action,
)
from core.exceptions import ExecutionError
from core.registry import Registry
from core.task import Task

logger = logging.getLogger(__name__)


class Executor:
    """Executes validated Task objects using registered tools."""

    def __init__(self, registry: Registry) -> None:
        self._registry = registry

    def execute(self, task: Task) -> Task:
        """Execute a single validated task.

        Lifecycle:
            PENDING → RUNNING → COMPLETED or FAILED

        Args:
            task: A validated Task in PENDING state.

        Returns:
            The same Task with updated status, result, or error.
        """
        # Claim the task atomically before resolving or calling any tool. A duplicate
        # invocation on RUNNING/terminal work must never repeat a side effect.
        if not task.try_start():
            logger.warning(
                "Skipping duplicate task execution for %s.%s in state %s",
                task.tool, task.action, getattr(task.status, "value", task.status),
            )
            return task

        try:
            tool_impl = self._registry.get_executor(task.tool)
        except Exception as exc:
            task.fail(f"NOT EXECUTED: executor lookup failed: {type(exc).__name__}: {exc}")
            logger.exception("Executor lookup failed for tool: %s", task.tool)
            return task

        if tool_impl is None:
            task.fail(f"NOT EXECUTED: no executor found for tool: {task.tool}")
            logger.error("No executor for tool: %s", task.tool)
            return task

        logger.info(
            "Executing: tool=%s action=%s args=%s",
            task.tool,
            task.action,
            task.args,
        )

        try:
            result = tool_impl.execute(task.action, task.args)
            task.complete(result)

            logger.info(
                "Completed: tool=%s action=%s result=%s",
                task.tool,
                task.action,
                result,
            )
        except ExecutionError as exc:
            if (
                is_known_read_only_action(task.tool, task.action)
                or is_known_pre_side_effect_failure(task.tool, task.action, str(exc))
            ):
                task.fail(str(exc))
            else:
                task.fail(
                    "OUTCOME UNKNOWN: execution raised after handler invocation: "
                    f"{exc}. Do not automatically retry until external state is reconciled."
                )
            logger.error("Execution failed: %s", exc)
        except Exception as exc:
            if (
                is_known_read_only_action(task.tool, task.action)
                or is_known_pre_side_effect_failure(task.tool, task.action, str(exc))
            ):
                task.fail(f"Execution failed: {exc}")
            else:
                task.fail(
                    "OUTCOME UNKNOWN: execution raised after handler invocation: "
                    f"{type(exc).__name__}: {exc}. Do not automatically retry until external state is reconciled."
                )
            logger.error(  # noqa: G201
                "Unexpected error in %s.%s: %s",
                task.tool,
                task.action,
                exc,
                exc_info=True,
            )

        return task

"""
Executor — runs validated Task objects against registered tools.

Takes a Task in PENDING state, transitions it through RUNNING
to COMPLETED or FAILED. Looks up the tool via the Registry and
delegates execution. Never parses JSON, never talks to the LLM.
"""

import logging

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
        tool_impl = self._registry.get_executor(task.tool)

        if tool_impl is None:
            if task.status in (TaskStatus.PENDING, TaskStatus.RETRYING):
                task.start()
            task.fail(f"No executor found for tool: {task.tool}")
            logger.error("No executor for tool: %s", task.tool)
            return task

        if task.status in (TaskStatus.PENDING, TaskStatus.RETRYING):
            task.start()

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
            task.fail(str(exc))
            logger.error("Execution failed: %s", exc)
        except Exception as exc:
            task.fail(f"Unexpected error: {exc}")
            logger.error(  # noqa: G201
                "Unexpected error in %s.%s: %s",
                task.tool,
                task.action,
                exc,
                exc_info=True,
            )

        return task

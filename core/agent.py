"""
Agent — top-level orchestrator of the Jarvis pipeline.

Receives user input and drives it through:
    Planner → Validator → Executor

Never parses JSON, never calls the LLM, never executes tools
directly. All dependencies are injected via the constructor.
"""

import logging

from core.exceptions import JarvisError
from core.executor import Executor
from core.planner import Planner
from core.task import Task, TaskStatus
from core.validator import Validator

logger = logging.getLogger(__name__)


class Agent:
    """Orchestrates the Jarvis agent pipeline.

    Receives fully constructed dependencies and coordinates
    the flow of data between them.
    """

    def __init__(
        self,
        planner: Planner,
        validator: Validator,
        executor: Executor,
    ) -> None:
        self._planner = planner
        self._validator = validator
        self._executor = executor

    def run(self, user_input: str) -> list[Task]:
        """Process user input through the full pipeline.

        Pipeline:
            1. Planner converts input to Task objects
            2. Each Task is validated against the Registry
            3. Valid Tasks are executed
            4. All Tasks are returned with their final states

        Args:
            user_input: Natural language instruction from the user.

        Returns:
            List of Task objects with status, result, and errors.
        """
        logger.info("Agent processing: %s", user_input)

        try:
            tasks = self._planner.plan(user_input)
        except JarvisError as exc:
            logger.error("Planning failed: %s", exc)
            return [self._error_task(str(exc))]

        results: list[Task] = []

        for task in tasks:
            result = self._process_task(task)
            results.append(result)

        completed = sum(
            1 for t in results if t.status == TaskStatus.COMPLETED
        )
        failed = sum(
            1 for t in results if t.status == TaskStatus.FAILED
        )

        logger.info(
            "Finished: %d task(s), %d completed, %d failed",
            len(results),
            completed,
            failed,
        )

        return results

    def _process_task(self, task: Task) -> Task:
        """Validate and execute a single task.

        Args:
            task: A Task in PENDING state.

        Returns:
            The Task with updated status after execution.
        """
        try:
            self._validator.validate(task)
        except JarvisError as exc:
            logger.warning("Validation failed: %s", exc)
            task.start()
            task.fail(str(exc))
            return task

        return self._executor.execute(task)

    @staticmethod
    def _error_task(error_message: str) -> Task:
        """Create a failed Task for pipeline-level errors.

        Args:
            error_message: Description of what went wrong.

        Returns:
            A Task in FAILED state with the error message.
        """
        task = Task(tool="system", action="error", args={})
        task.start()
        task.fail(error_message)

        return task
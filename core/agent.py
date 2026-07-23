"""
Agent — top-level orchestrator of the Jarvis pipeline.

Receives user input and drives it through:
    Planner → Validator → Executor

Optionally integrates with Memory to provide conversational
context across interactions. Memory is injected via constructor
and is fully optional — if None, the pipeline works identically.

Never parses JSON, never calls the LLM, never executes tools
directly. All dependencies are injected via the constructor.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from core.exceptions import JarvisError
from core.executor import Executor
from core.planner import Planner
from core.task import Task, TaskStatus
from core.validator import Validator

if TYPE_CHECKING:
    from memory.memory_manager import MemoryManager

logger = logging.getLogger(__name__)


class Agent:
    """Orchestrates the Jarvis agent pipeline.

    Receives fully constructed dependencies and coordinates
    the flow of data between them. Memory integration is
    optional and never crashes the pipeline.
    """

    def __init__(
        self,
        planner: Planner,
        validator: Validator,
        executor: Executor,
        memory: MemoryManager | None = None,
    ) -> None:
        self._planner = planner
        self._validator = validator
        self._executor = executor
        self._memory = memory

    def run(self, user_input: str) -> list[Task]:
        """Process user input through the full pipeline.

        Pipeline:
            1. Load conversation context from memory (if available)
            2. Planner converts input + context into Task objects
            3. Each Task is validated against the Registry
            4. Valid Tasks are executed
            5. Results are stored in memory (if available)
            6. All Tasks are returned with their final states

        Args:
            user_input: Natural language instruction from the user.

        Returns:
            List of Task objects with status, result, and errors.
        """
        logger.info("Agent processing: %s", user_input)

        # Load context from memory
        context = self._load_context()

        try:
            tasks = self._planner.plan(user_input, context=context)
        except JarvisError as exc:
            logger.error("Planning failed: %s", exc)
            return [self._error_task(str(exc))]

        results: list[Task] = []

        for task in tasks:
            result = self._process_task(task)
            results.append(result)

        # Store interaction in memory
        self._save_to_memory(user_input, results)

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

    def _load_context(self) -> str:
        """Load conversation context from memory.

        Returns:
            Formatted context string, or empty string if memory
            is unavailable or retrieval fails.
        """
        if self._memory is None:
            return ""

        try:
            context = self._memory.get_context()
            return context.formatted
        except Exception as exc:
            logger.warning("Failed to load memory context: %s", exc)
            return ""

    def _save_to_memory(
        self, user_input: str, tasks: list[Task]
    ) -> None:
        """Store the current interaction in memory.

        Args:
            user_input: The user's original input.
            tasks: Executed tasks with final states.
        """
        if self._memory is None:
            return

        try:
            self._memory.store_interaction(user_input, tasks)
        except Exception as exc:
            logger.warning("Failed to save to memory: %s", exc)

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
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
import re
from pathlib import Path
from typing import TYPE_CHECKING

from core.exceptions import JarvisError
from core.executor import Executor
from core.planner import Planner
from core.task import Task, TaskStatus
from core.validator import Validator

if TYPE_CHECKING:
    from memory.memory_manager import MemoryManager

logger = logging.getLogger(__name__)
_MEMORY_FAILURES = (AttributeError, OSError, RuntimeError, TypeError, ValueError)


import time

from core.cognition.enums import DecisionType
from core.cognition.manager import CognitiveManager


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
        cognitive_manager: CognitiveManager | None = None,
    ) -> None:
        self._planner = planner
        self._validator = validator
        self._executor = executor
        self._memory = memory
        self._cognitive_manager = cognitive_manager

    def run(self, user_input: str) -> list[Task]:
        """Process user input through the full pipeline.

        Pipeline:
            1. Load conversation context from memory (if available)
            2. CognitiveManager analyzes and decides (if available)
            3. Planner converts input + context into Task objects if needed
            4. Each Task is validated against the Registry
            5. Valid Tasks are executed
            6. Results are stored in memory (if available)
            7. All Tasks are returned with their final states

        Args:
            user_input: Natural language instruction from the user.

        Returns:
            List of Task objects with status, result, and errors.
        """
        logger.info("Agent processing: %s", user_input)

        start_time = time.time()
        context = self._load_context()
        tasks = []
        intent_result = None

        memory_response = self._handle_personal_memory(user_input)
        if memory_response is not None:
            tasks = [
                Task(tool="system", action="respond", args={"message": memory_response})
            ]
        elif self._cognitive_manager:
            intent_result = self._cognitive_manager.analyze(user_input)
            decision = self._cognitive_manager.decide(intent_result)

            if decision.decision_type == DecisionType.DIRECT_RESPONSE:
                msg = self._direct_response(user_input)
                tasks = [Task(tool="system", action="respond", args={"message": msg})]
            elif decision.decision_type == DecisionType.ASK_CLARIFICATION:
                msg = "I'm not quite sure what you mean. Could you please clarify?"
                tasks = [Task(tool="system", action="respond", args={"message": msg})]
            elif decision.decision_type == DecisionType.EXECUTE_ACTION:
                parameters = dict(intent_result.parameters)
                tool = parameters.pop("tool", "windows")
                action = intent_result.extracted_action or "open_app"
                tasks = [Task(tool=tool, action=action, args=parameters)]
            else:  # CREATE_PLAN
                try:
                    tasks = self._planner.plan(user_input, context=context)
                except JarvisError as exc:
                    logger.error("Planning failed: %s", exc)
                    tasks = [
                        self._error_task(
                            "I couldn't plan that request just now. Please try again."
                        )
                    ]
        else:
            try:
                tasks = self._planner.plan(user_input, context=context)
            except JarvisError as exc:
                logger.error("Planning failed: %s", exc)
                tasks = [
                    self._error_task(
                        "I couldn't plan that request just now. Please try again."
                    )
                ]

        results: list[Task] = []

        for task in tasks:
            result = self._process_task(task)
            results.append(result)

        # Store interaction in memory
        self._save_to_memory(user_input, results)

        if self._cognitive_manager and intent_result:
            execution_time = time.time() - start_time
            success = not any(t.status == TaskStatus.FAILED for t in results)
            main_action = tasks[0].action if tasks else "none"
            self._cognitive_manager.reflect(
                user_input=user_input,
                intent=intent_result.intent,
                action=main_action,
                success=success,
                execution_time=execution_time,
            )

        completed = sum(1 for t in results if t.status == TaskStatus.COMPLETED)
        failed = sum(1 for t in results if t.status == TaskStatus.FAILED)

        logger.info(
            "Finished: %d task(s), %d completed, %d failed",
            len(results),
            completed,
            failed,
        )

        return results

    def _handle_personal_memory(self, user_input: str) -> str | None:
        """Handle explicit personal-memory requests without an LLM round trip."""
        if self._memory is None:
            return None

        text = user_input.strip()
        remember_match = re.fullmatch(
            r"remember(?: that)? my (.+?) is (.+)", text, flags=re.IGNORECASE
        )
        if remember_match:
            key, value = remember_match.groups()
            try:
                self._memory.remember_fact(key, value)
            except _MEMORY_FAILURES as exc:
                logger.warning("Failed to store personal memory: %s", exc)
                return "I couldn't save that memory just now. Please try again."
            return f"I'll remember that your {key.strip()} is {value.strip()}."

        name_match = re.fullmatch(r"my name is (.+)", text, flags=re.IGNORECASE)
        if name_match:
            name = name_match.group(1).strip()
            try:
                self._memory.remember_fact("name", name)
            except _MEMORY_FAILURES as exc:
                logger.warning("Failed to store user name: %s", exc)
                return "I couldn't save your name just now. Please try again."
            return f"Nice to meet you, {name}. I'll remember your name."

        lowered = text.lower().strip().rstrip("?!.")
        if lowered in {
            "who am i",
            "what is my name",
            "can you say my name",
            "do you know my name",
        }:
            value = self._recall_personal_fact("name")
            return f"Your name is {value}." if value else None

        recall_match = re.fullmatch(
            r"(?:what is|what's) my (.+)", lowered, flags=re.IGNORECASE
        )
        if recall_match:
            key = recall_match.group(1)
            value = self._recall_personal_fact(key)
            if value:
                return f"Your {key} is {value}."
        return None

    def _recall_personal_fact(self, key: str) -> str | None:
        """Retrieve one user fact without exposing memory backend errors."""
        try:
            return self._memory.recall_fact(key) if self._memory else None
        except _MEMORY_FAILURES as exc:
            logger.warning("Failed to recall personal memory: %s", exc)
            return None

    @staticmethod
    def _direct_response(user_input: str) -> str:
        """Return deterministic, user-facing responses for common conversation."""
        text = user_input.lower().strip().rstrip("?!.")
        if text in {"hello", "hi", "hey"}:
            return "Hello! How can I help you today?"
        if text == "who are you":
            return (
                "I'm JARVIS, your AI Operating System. I can help automate "
                "your computer, answer questions, write code, manage projects, "
                "control applications, and assist you intelligently."
            )
        if text == "what can you do":
            return (
                "I can open applications and websites, search the web, manage "
                "files, help with projects, and remember useful context from our "
                "conversation. What would you like to do?"
            )
        if text in {
            "who am i",
            "what is my name",
            "can you say my name",
            "do you know my name",
        }:
            return (
                "I don't know your name from this conversation yet. Tell me what "
                "you'd like me to call you, and I can remember it."
            )
        if text in {"what is my current workspace", "where is my current workspace"}:
            return f"Your current workspace is {Path.cwd()}."
        return "How can I help you today?"

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
        except _MEMORY_FAILURES as exc:
            logger.warning("Failed to load memory context: %s", exc)
            return ""

    def _save_to_memory(self, user_input: str, tasks: list[Task]) -> None:
        """Store the current interaction in memory.

        Args:
            user_input: The user's original input.
            tasks: Executed tasks with final states.
        """
        if self._memory is None:
            return

        try:
            self._memory.store_interaction(user_input, tasks)
        except _MEMORY_FAILURES as exc:
            logger.warning("Failed to save to memory: %s", exc)

    def _process_task(self, task: Task) -> Task:
        """Validate and execute a single task.

        Args:
            task: A Task in PENDING state.

        Returns:
            The Task with updated status after execution.
        """
        # Handle conversational responses from the LLM directly —
        # these don't go through validation or execution.
        if task.tool == "system" and task.action == "respond":
            message = task.args.get("message", "")
            task.start()
            task.complete(message)
            return task

        try:
            self._validator.validate(task)
        except JarvisError as exc:
            logger.warning("Validation failed: %s", exc)
            task.start()
            task.fail(self._friendly_error_message(str(exc)))
            return task

        result = self._executor.execute(task)
        if result.status == TaskStatus.FAILED:
            logger.warning("Execution failed: %s", result.error)
            result.error = self._friendly_error_message(result.error)
        return result

    @staticmethod
    def _friendly_error_message(error: str) -> str:
        """Translate internal tool errors into concise, safe user messages."""
        normalized = error.lower()
        if "already exists" in normalized:
            return "That file or folder already exists. Please choose another name."
        if "path does not exist" in normalized or "cannot be empty" in normalized:
            return "I couldn't access that path. Please check it and try again."
        if "unknown tool" in normalized or "unknown action" in normalized:
            return "I couldn't find a safe action for that request. Please rephrase it."
        if "missing required argument" in normalized or "cannot be none" in normalized:
            return "I need a little more information to complete that request."
        if "timeout" in normalized:
            return "That took too long to complete. Please try again in a moment."
        return "I couldn't complete that request. Please try again or rephrase it."

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

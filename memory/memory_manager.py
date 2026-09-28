"""
Memory manager — high-level interface for the Agent.

Sits between the Agent and the memory backend. Handles
serialization of Task objects into storable entries, and
formats retrieved history into context strings ready for
LLM prompt injection.
"""

import logging
from typing import Any

from core.task import Task, TaskStatus
from memory.base_memory import BaseMemory
from memory.models import MemoryContext, MemoryEntry

logger = logging.getLogger(__name__)

_MAX_CONTEXT_ENTRIES = 5


class MemoryManager:
    """High-level memory interface for the Agent.

    Responsibilities:
        - Serialize Task objects into MemoryEntry records
        - Retrieve recent history and format it for LLM context
        - Shield the Agent from memory backend details
    """

    def __init__(
        self,
        memory: BaseMemory,
        context_limit: int = _MAX_CONTEXT_ENTRIES,
    ) -> None:
        """Initialize the memory manager.

        Args:
            memory: A BaseMemory implementation for storage.
            context_limit: Max entries to include in context.
        """
        self._memory = memory
        self._context_limit = context_limit

    def store_interaction(self, user_input: str, tasks: list[Task]) -> None:
        """Store a complete interaction (user input + task results).

        Args:
            user_input: The user's original input.
            tasks: List of executed Task objects with final states.
        """
        serialized = self._serialize_tasks(tasks)
        summary = self._build_summary(user_input, tasks)

        entry = MemoryEntry(
            user_input=user_input,
            tasks=serialized,
            summary=summary,
        )

        try:
            self._memory.store(entry)
            logger.debug("Stored interaction: %s", entry.id)
        except Exception:
            logger.exception("Failed to store interaction")

    def get_context(self) -> MemoryContext:
        """Retrieve recent conversation history as formatted context.

        Returns:
            MemoryContext with entries and a formatted string
            ready for LLM prompt injection. Returns empty context
            if retrieval fails.
        """
        try:
            entries = self._memory.get_recent(self._context_limit)
        except Exception:
            logger.exception("Failed to retrieve context")
            return MemoryContext()

        if not entries:
            return MemoryContext()

        formatted = self._format_context(entries)

        return MemoryContext(entries=entries, formatted=formatted)

    def remember_fact(self, key: str, value: str) -> None:
        """Persist a concise user fact for direct recall in future turns."""
        normalized_key = self._normalize_fact_key(key)
        normalized_value = value.strip()
        if not normalized_key or not normalized_value:
            raise ValueError("A memory fact needs both a key and a value.")
        self._memory.store_fact(normalized_key, normalized_value)

    def recall_fact(self, key: str) -> str | None:
        """Look up a previously saved user fact."""
        normalized_key = self._normalize_fact_key(key)
        return self._memory.get_fact(normalized_key) if normalized_key else None

    @staticmethod
    def _normalize_fact_key(key: str) -> str:
        """Make equivalent user-memory labels map to the same storage key."""
        return " ".join(key.lower().strip().split())

    @staticmethod
    def _serialize_tasks(tasks: list[Task]) -> list[dict[str, Any]]:
        """Convert Task objects into serializable dicts.

        Args:
            tasks: List of Task objects.

        Returns:
            List of dicts with tool, action, status, result, error.
        """
        return [
            {
                "tool": task.tool,
                "action": task.action,
                "status": task.status.value
                if hasattr(task.status, "value")
                else str(task.status),
                "result": str(task.result) if task.result else "",
                "error": task.error,
            }
            for task in tasks
        ]

    @staticmethod
    def _build_summary(user_input: str, tasks: list[Task]) -> str:
        """Build a one-line summary of the interaction.

        Args:
            user_input: The user's input.
            tasks: Executed tasks.

        Returns:
            Summary string like "User asked to open calculator → completed"
        """
        completed = sum(1 for t in tasks if t.status == TaskStatus.COMPLETED)
        failed = sum(1 for t in tasks if t.status == TaskStatus.FAILED)

        parts = []

        if completed:
            parts.append(f"{completed} completed")
        if failed:
            parts.append(f"{failed} failed")

        status = ", ".join(parts) if parts else "no tasks"
        truncated = user_input[:80]

        return f"{truncated} → {status}"

    @staticmethod
    def _format_context(entries: list[MemoryEntry]) -> str:
        """Format memory entries into a string for LLM context.

        Entries are formatted in chronological order (oldest first)
        so the LLM sees the conversation flow naturally.

        Args:
            entries: List of MemoryEntry objects (most recent first).

        Returns:
            Formatted context string.
        """
        # Reverse so oldest is first (entries come most-recent-first)
        chronological = list(reversed(entries))

        lines: list[str] = ["Previous conversation:"]

        for entry in chronological:
            lines.append(f"- User: {entry.user_input}")

            for task in entry.tasks:
                status = task.get("status", "unknown")
                result = task.get("result", "")
                error = task.get("error", "")

                if status == "completed" and result:
                    lines.append(f"  Result: {result}")
                elif status == "failed" and error:
                    lines.append(f"  Error: {error}")

        return "\n".join(lines)

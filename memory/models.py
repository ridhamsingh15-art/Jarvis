"""
Data models for the Jarvis memory subsystem.

Defines the structures used to store and retrieve conversation
history. All models are dataclasses for consistency with the
rest of the framework.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


@dataclass
class MemoryEntry:
    """One conversation turn stored in memory.

    Attributes:
        id: Unique identifier (UUID).
        timestamp: When this interaction occurred (UTC).
        user_input: The user's original natural language input.
        tasks: Serialized task results as list of dicts, each
            containing tool, action, status, result, and error.
        summary: Optional one-line summary of the interaction.
    """

    user_input: str
    tasks: list[dict[str, Any]] = field(default_factory=list)
    summary: str = ""
    id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


@dataclass
class MemoryContext:
    """Context bundle passed to the Planner for LLM injection.

    Attributes:
        entries: Recent conversation history as MemoryEntry objects.
        formatted: Pre-formatted string ready for prompt injection.
    """

    entries: list[MemoryEntry] = field(default_factory=list)
    formatted: str = ""

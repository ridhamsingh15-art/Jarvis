"""
Abstract base class for the Jarvis memory backend.

Defines the interface that all memory implementations must
fulfill. This allows swapping SQLite for a vector DB, Redis,
or any other storage without touching the rest of the framework.
"""

from abc import ABC, abstractmethod

from memory.models import MemoryEntry


class BaseMemory(ABC):
    """Contract that every memory backend must implement."""

    @abstractmethod
    def store(self, entry: MemoryEntry) -> None:
        """Persist a memory entry.

        Args:
            entry: The MemoryEntry to store.

        Raises:
            MemoryError: If the storage operation fails.
        """

    @abstractmethod
    def get_recent(self, limit: int = 10) -> list[MemoryEntry]:
        """Retrieve the most recent memory entries.

        Args:
            limit: Maximum number of entries to return.

        Returns:
            List of MemoryEntry objects, most recent first.
        """

    @abstractmethod
    def search(self, query: str, limit: int = 5) -> list[MemoryEntry]:
        """Search memory entries by keyword.

        Args:
            query: Search term to match against user input and summary.
            limit: Maximum number of results.

        Returns:
            List of matching MemoryEntry objects.
        """

    @abstractmethod
    def clear(self) -> None:
        """Delete all memory entries.

        Raises:
            MemoryError: If the clear operation fails.
        """

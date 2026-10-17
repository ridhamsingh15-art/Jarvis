"""Jarvis core package.

Keep package initialization dependency-free so low-level domain modules can
import ``core.exceptions`` without accidentally loading the entire agent stack.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.agent import Agent

__all__ = ["Agent"]


def __getattr__(name: str) -> object:
    """Lazily expose high-level types without creating import cycles."""
    if name == "Agent":
        from core.agent import Agent

        return Agent
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

"""Stable data models for future adaptive-learning integrations."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class Experience:
    """An immutable record of an input, selected action, and outcome."""

    user_input: str
    plan: list[dict[str, Any]]
    success: bool
    confidence: float
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

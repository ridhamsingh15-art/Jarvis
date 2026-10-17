"""Feedback contract for future learning policy evaluation."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Feedback:
    """Optional human or system assessment of an execution."""

    successful: bool
    note: str = ""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


def normalize_step_indexes(values: Any, step_count: int) -> list[int]:
    # Approval indexes are authorization state. JSON boolean true becomes Python
    # True, and True == 1; accepting it would authorize step index 1.
    # Invalid entries are discarded fail-closed rather than coerced.
    if type(step_count) is not int or step_count < 0 or not isinstance(values, list):
        return []
    valid: list[int] = []
    seen: set[int] = set()
    for value in values:
        if type(value) is not int or not 0 <= value < step_count or value in seen:
            continue
        seen.add(value)
        valid.append(value)
    return valid


class MissionState(StrEnum):
    DRAFT = "DRAFT"
    PLANNED = "PLANNED"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    BLOCKED = "BLOCKED"
    RECOVERING = "RECOVERING"
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    ABANDONED = "ABANDONED"
    ARCHIVED = "ARCHIVED"


@dataclass
class Mission:
    id: str
    objective: str
    state: MissionState = MissionState.DRAFT
    steps: list[str] = field(default_factory=list)
    completed_steps: list[str] = field(default_factory=list)
    pending_approvals: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    approved_steps: list[str] = field(default_factory=list)
    # Occurrence-specific approval state; indices are zero-based and survive duplicate step text.
    pending_approval_indexes: list[int] = field(default_factory=list)
    approved_step_indexes: list[int] = field(default_factory=list)
    step_results: list[dict[str, Any]] = field(default_factory=list)
    failure_reason: str = ""

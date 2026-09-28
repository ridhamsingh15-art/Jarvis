from dataclasses import dataclass, field
from enum import StrEnum


class MissionState(StrEnum):
    DRAFT = "DRAFT"
    PLANNED = "PLANNED"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    BLOCKED = "BLOCKED"
    RECOVERING = "RECOVERING"
    COMPLETED = "COMPLETED"
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

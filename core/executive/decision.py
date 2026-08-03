from dataclasses import dataclass, field
from enum import StrEnum

from core.models import JarvisModel


class ExecutiveDecision(StrEnum):
    PROCEED = "PROCEED"
    CLARIFY = "CLARIFY"
    DEFER = "DEFER"
    DELEGATE = "DELEGATE"
    CANCEL = "CANCEL"
    PAUSE = "PAUSE"
    RESUME = "RESUME"
    ESCALATE = "ESCALATE"

@dataclass(frozen=True)
class DecisionContext(JarvisModel):
    goal_id: str
    confidence: float
    risk: float
    urgency: float
    sources: list[str] = field(default_factory=list)

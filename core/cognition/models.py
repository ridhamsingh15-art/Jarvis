from dataclasses import dataclass, field
from typing import Any

from core.cognition.enums import DecisionType, IntentType
from core.models.base import JarvisModel


@dataclass(frozen=True, slots=True)
class IntentResult(JarvisModel):
    intent: IntentType
    confidence: float
    extracted_action: str | None = None
    parameters: dict[str, Any] = field(default_factory=dict)
    reasoning: str = ""

@dataclass(frozen=True, slots=True)
class CognitiveDecision(JarvisModel):
    decision_type: DecisionType
    intent_result: IntentResult
    target_component: str

@dataclass(frozen=True, slots=True)
class ExperienceRecord(JarvisModel):
    user_input: str
    intent: IntentType
    action: str
    success: bool
    execution_time: float
    timestamp: str

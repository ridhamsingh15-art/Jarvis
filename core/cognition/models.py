from dataclasses import dataclass, field
from enum import Enum
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

class MemoryType(Enum):
    IDENTITY = "identity"
    PREFERENCE = "preference"
    PROJECT = "project"
    GOAL = "goal"
    SKILL = "skill"
    FACT = "fact"
    CONTEXT = "context"
    SUMMARY = "summary"

@dataclass
class RetrievedMemory:
    """A single piece of retrieved memory or knowledge."""
    content: str
    source: str  # "sqlite", "pki", "context"
    relevance_score: float = 0.0
    memory_type: MemoryType | str = MemoryType.FACT

@dataclass
class CognitiveContext:
    """The structured context injected into the prompt."""
    user_facts: list[str] = field(default_factory=list)
    recent_context: list[str] = field(default_factory=list)
    pki_results: list[str] = field(default_factory=list)
    active_projects: list[str] = field(default_factory=list)

@dataclass
class ReflectionResult:
    """The outcome of a post-conversation reflection."""
    should_remember: bool = False
    facts_to_store: list[tuple[str, str]] = field(default_factory=list)  # [(key, value)]
    facts_to_update: list[tuple[str, str]] = field(default_factory=list)
    facts_to_delete: list[str] = field(default_factory=list)
    reasoning: str = ""

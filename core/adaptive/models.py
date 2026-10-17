from dataclasses import dataclass, field

from core.models import JarvisModel
from core.models.primitives import Identifier, Metadata, Timestamp

from .enums import LearningDecision, PatternType


@dataclass(frozen=True, slots=True)
class Experience(JarvisModel):
    """Immutable representation of an execution experience."""
    user_input: str
    success: bool
    duration: float
    id: Identifier = field(default_factory=Identifier)
    timestamp: Timestamp = field(default_factory=Timestamp)
    intent: str | None = None
    workflow_id: Identifier | None = None
    skill_id: Identifier | None = None
    tasks: list[str] = field(default_factory=list)
    metadata: Metadata = field(default_factory=Metadata)


@dataclass(frozen=True, slots=True)
class LearningPattern(JarvisModel):
    """Immutable representation of a detected learning pattern."""
    pattern_type: PatternType
    occurrences: int
    confidence: float
    source_experiences: list[Identifier]
    id: Identifier = field(default_factory=Identifier)
    metadata: Metadata = field(default_factory=Metadata)


@dataclass(frozen=True, slots=True)
class LearningRecommendation(JarvisModel):
    """Immutable representation of a learning recommendation."""
    decision: LearningDecision
    reason: str
    confidence: float
    target_skill: Identifier | None = None
    metadata: Metadata = field(default_factory=Metadata)


@dataclass(frozen=True, slots=True)
class OptimizationPlan(JarvisModel):
    """Immutable representation of an optimization plan."""
    skill_confidence_adjustments: dict[str, float] = field(default_factory=dict)
    preferred_workflows: list[str] = field(default_factory=list)
    planner_hints: list[str] = field(default_factory=list)

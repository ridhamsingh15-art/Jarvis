import builtins
from dataclasses import dataclass, field
from typing import Any

from core.models import JarvisModel
from core.models.primitives import Identifier, Timestamp

from .enums import GoalPriority, GoalState, RetryStrategy, StepState


@dataclass(frozen=True, slots=True)
class Goal(JarvisModel):
    """Abstract objective tracking structure."""
    id: Identifier
    description: str
    state: GoalState = GoalState.CREATED
    priority: GoalPriority = GoalPriority.NORMAL
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: Timestamp = field(default_factory=Timestamp)


@dataclass(frozen=True, slots=True)
class GoalStep(JarvisModel):
    """Granular task execution primitive."""
    id: Identifier
    description: str
    state: StepState = StepState.PENDING
    dependencies: builtins.list[Identifier] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)
    retry_strategy: RetryStrategy = RetryStrategy.LINEAR
    max_retries: int = 3
    retry_count: int = 0


@dataclass(frozen=True, slots=True)
class GoalPlan(JarvisModel):
    """Hierarchical representation aggregating GoalStep lists."""
    goal_id: Identifier
    steps: builtins.list[GoalStep] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class GoalProgress(JarvisModel):
    """Real-time percentage tracker mapping execution."""
    goal_id: Identifier
    percentage: float
    current_step: Identifier | None = None
    timestamp: Timestamp = field(default_factory=Timestamp)


@dataclass(frozen=True, slots=True)
class GoalHistory(JarvisModel):
    """Eventual consistency tracker retaining past state executions."""
    goal_id: Identifier
    logs: builtins.list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class GoalEvaluation(JarvisModel):
    """End-of-state structural evaluation mapping completion success."""
    goal_id: Identifier
    success: bool
    metrics: dict[str, Any] = field(default_factory=dict)

import builtins
from dataclasses import dataclass, field
from typing import Any

from core.models import JarvisModel
from core.models.primitives import Identifier, Timestamp

from .enums import (
    MetricType,
    OptimizationCategory,
    RecommendationStatus,
    TrendDirection,
)


@dataclass(frozen=True, slots=True)
class SystemMetric(JarvisModel):
    """Granular tracking struct mapping type, value, and context tags."""
    id: Identifier
    type: MetricType
    value: float
    context: dict[str, Any] = field(default_factory=dict)
    timestamp: Timestamp = field(default_factory=Timestamp)


@dataclass(frozen=True, slots=True)
class MetricSnapshot(JarvisModel):
    """Aggregated bucket of metrics recorded at a specific timestamp."""
    id: Identifier
    metrics: builtins.list[SystemMetric] = field(default_factory=list)
    timestamp: Timestamp = field(default_factory=Timestamp)


@dataclass(frozen=True, slots=True)
class PerformanceTrend(JarvisModel):
    """Evaluator output comparing past/current metrics and deducing direction."""
    metric_type: MetricType
    direction: TrendDirection
    delta_percentage: float
    context: str = ""


@dataclass(frozen=True, slots=True)
class OptimizationRecommendation(JarvisModel):
    """Output suggesting specific behavioral tuning (never modifies source)."""
    id: Identifier
    category: OptimizationCategory
    target: str  # e.g. "skill_id", "provider_id"
    suggested_value: float
    rationale: str
    status: RecommendationStatus = RecommendationStatus.PENDING
    timestamp: Timestamp = field(default_factory=Timestamp)


@dataclass(frozen=True, slots=True)
class HealthScore(JarvisModel):
    """Overall rating aggregated from system latency, completion success, etc."""
    score: float  # 0.0 to 100.0
    timestamp: Timestamp = field(default_factory=Timestamp)


@dataclass(frozen=True, slots=True)
class ImprovementReport(JarvisModel):
    """Full structural wrapper containing HealthScore, trends, and recommendations."""
    id: Identifier
    health_score: HealthScore
    trends: builtins.list[PerformanceTrend] = field(default_factory=list)
    recommendations: builtins.list[OptimizationRecommendation] = field(default_factory=list)
    timestamp: Timestamp = field(default_factory=Timestamp)

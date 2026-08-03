import builtins
import uuid

from core.models.primitives import Identifier

from .interfaces import IImprovementRecommender
from .models import (
    HealthScore,
    ImprovementReport,
    MetricSnapshot,
    OptimizationRecommendation,
    PerformanceTrend,
)


class DefaultImprovementRecommender(IImprovementRecommender):
    """Orchestrates analysis and optimization flows into structured reports."""

    def generate_report(
        self, 
        snapshot: MetricSnapshot, 
        trends: builtins.list[PerformanceTrend], 
        recommendations: builtins.list[OptimizationRecommendation]
    ) -> ImprovementReport:
        
        # Trivially calculate health based on recommendations length
        score_value = max(0.0, 100.0 - (len(recommendations) * 5.0))
        health = HealthScore(score=score_value)
        
        return ImprovementReport(
            id=Identifier(f"report_{uuid.uuid4().hex[:8]}"),
            health_score=health,
            trends=trends,
            recommendations=recommendations
        )

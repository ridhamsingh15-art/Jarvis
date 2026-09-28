import builtins
import uuid
from typing import Any

from core.models.primitives import Identifier

from .enums import OptimizationCategory
from .interfaces import IBehaviorOptimizer
from .models import OptimizationRecommendation


class DefaultBehaviorOptimizer(IBehaviorOptimizer):
    """Suggests configuration adjustments safely limiting scope without touching code."""

    def optimize(self, analysis_results: dict[str, Any]) -> builtins.list[OptimizationRecommendation]:
        recs = []
        
        # Example optimization logic
        for latency_metric in analysis_results.get("high_latency", []):
            provider_id = latency_metric.context.get("provider_id", "default")
            recs.append(
                OptimizationRecommendation(
                    id=Identifier(f"rec_{uuid.uuid4().hex[:8]}"),
                    category=OptimizationCategory.PROVIDER_PRIORITY,
                    target=provider_id,
                    suggested_value=0.5, # Down-weight priority
                    rationale=f"High latency observed for provider {provider_id}."
                )
            )
            
        return recs

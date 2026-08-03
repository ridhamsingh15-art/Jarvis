import builtins

from .enums import TrendDirection
from .interfaces import ITrendEvaluator
from .models import MetricSnapshot, PerformanceTrend


class DefaultTrendEvaluator(ITrendEvaluator):
    """Computes regressions historically based on recent snapshots."""

    def evaluate(self, current: MetricSnapshot, historical: builtins.list[MetricSnapshot]) -> builtins.list[PerformanceTrend]:
        if not historical:
            return []
            
        # Compare current values to the immediate previous snapshot
        prev_snap = historical[-1]
        
        prev_vals = {}
        for m in prev_snap.metrics:
            prev_vals[m.type] = m.value
            
        trends = []
        for m in current.metrics:
            if m.type in prev_vals:
                prev_val = prev_vals[m.type]
                delta = m.value - prev_val
                
                direction = TrendDirection.STABLE
                if delta > 0:
                    direction = TrendDirection.IMPROVING if m.type.name != "LATENCY" else TrendDirection.DEGRADING
                elif delta < 0:
                    direction = TrendDirection.DEGRADING if m.type.name != "LATENCY" else TrendDirection.IMPROVING
                    
                trends.append(PerformanceTrend(
                    metric_type=m.type,
                    direction=direction,
                    delta_percentage=(delta / prev_val * 100) if prev_val else 0.0,
                    context="Compared to previous snapshot"
                ))
                
        return trends

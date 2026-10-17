from typing import Any

from .enums import MetricType
from .interfaces import ISystemAnalyzer
from .models import MetricSnapshot


class DefaultSystemAnalyzer(ISystemAnalyzer):
    """Analyzes aggregated metrics identifying bottlenecks (e.g. latency)."""

    def analyze(self, snapshot: MetricSnapshot) -> dict[str, Any]:
        results: dict[str, Any] = {
            "high_latency": [],
            "low_success": []
        }
        
        for metric in snapshot.metrics:
            if metric.type == MetricType.LATENCY and metric.value > 1000.0:
                results["high_latency"].append(metric)
                
            if metric.type == MetricType.TASK_SUCCESS and metric.value < 0.5:
                results["low_success"].append(metric)
                
        return results

from typing import Any

from .interfaces import Evaluator
from .models import Experience


class MetricsEvaluator(Evaluator):
    """
    Computes performance metrics and confidence scores over experiences.
    """

    def evaluate(self, experiences: list[Experience]) -> dict[str, Any]:
        total = len(experiences)
        if total == 0:
            return {
                "success_rate": 0.0,
                "failure_rate": 0.0,
                "average_duration": 0.0,
                "median_duration": 0.0,
                "execution_count": 0,
                "confidence": 0.0
            }

        successful = sum(1 for e in experiences if e.success)
        failed = total - successful
        
        success_rate = successful / total
        failure_rate = failed / total
        
        durations = sorted([e.duration for e in experiences])
        avg_duration = sum(durations) / total
        
        mid = total // 2
        if total % 2 == 0:
            median_duration = (durations[mid - 1] + durations[mid]) / 2.0
        else:
            median_duration = durations[mid]

        # Confidence heuristic: scales with occurrences up to a cap (e.g. 10)
        # combined with success consistency.
        confidence = success_rate * min(1.0, total / 10.0)

        return {
            "success_rate": success_rate,
            "failure_rate": failure_rate,
            "average_duration": avg_duration,
            "median_duration": median_duration,
            "execution_count": total,
            "confidence": confidence
        }

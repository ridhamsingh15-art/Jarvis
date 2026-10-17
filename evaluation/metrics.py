import threading
from dataclasses import dataclass

from .judge import Verdict
from .scenarios import ScenarioResult


@dataclass
class CategoryMetrics:
    """Aggregated metrics for a single evaluation category."""

    category: str
    total_cases: int = 0
    passed: int = 0
    failed: int = 0
    avg_latency_ms: float = 0.0
    total_tokens: int = 0
    total_memory_bytes: int = 0
    avg_quality: float = 0.0

    @property
    def success_rate(self) -> float:
        if self.total_cases == 0:
            return 0.0
        return self.passed / self.total_cases

    @property
    def failure_rate(self) -> float:
        if self.total_cases == 0:
            return 0.0
        return self.failed / self.total_cases


class EvaluationMetrics:
    """Thread-safe aggregation of raw scenario results and verdicts into
    structured performance metrics."""

    def __init__(self) -> None:
        self._categories: dict[str, CategoryMetrics] = {}
        self._lock = threading.RLock()

    def aggregate(
        self,
        category: str,
        results: list[ScenarioResult],
        verdicts: list[Verdict],
    ) -> CategoryMetrics:
        with self._lock:
            cm = CategoryMetrics(category=category)
            cm.total_cases = len(results)
            cm.passed = sum(1 for v in verdicts if v.passed)
            cm.failed = cm.total_cases - cm.passed

            if results:
                cm.avg_latency_ms = round(
                    sum(r.elapsed_ms for r in results) / len(results), 3
                )
                cm.total_tokens = sum(r.token_count for r in results)
                cm.total_memory_bytes = sum(r.memory_bytes for r in results)

            if verdicts:
                cm.avg_quality = round(
                    sum(v.quality_score for v in verdicts) / len(verdicts), 4
                )

            self._categories[category] = cm
            return cm

    def get_category(self, category: str) -> CategoryMetrics | None:
        with self._lock:
            return self._categories.get(category)

    def all_metrics(self) -> list[CategoryMetrics]:
        with self._lock:
            return list(self._categories.values())

    def overall_success_rate(self) -> float:
        with self._lock:
            total = sum(m.total_cases for m in self._categories.values())
            passed = sum(m.passed for m in self._categories.values())
            if total == 0:
                return 0.0
            return passed / total

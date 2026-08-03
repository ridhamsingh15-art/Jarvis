from dataclasses import dataclass

from .benchmark import BenchmarkSuite
from .judge import EvaluationJudge
from .metrics import EvaluationMetrics


@dataclass(frozen=True)
class RegressionResult:
    """Immutable comparison between baseline and current benchmark scores."""

    category: str
    baseline_success_rate: float
    current_success_rate: float
    delta: float
    regressed: bool


class RegressionRunner:
    """Runs the full benchmark suite and compares results against a stored
    baseline to detect regressions."""

    def __init__(
        self,
        suite: BenchmarkSuite,
        judge: EvaluationJudge,
        threshold: float = 0.05,
    ) -> None:
        self._suite = suite
        self._judge = judge
        self._threshold = threshold
        self._baseline: dict[str, float] = {}

    def set_baseline(self, baselines: dict[str, float]) -> None:
        """Set per-category baseline success rates."""
        self._baseline = dict(baselines)

    def capture_baseline(self) -> dict[str, float]:
        """Run the full suite and capture results as the new baseline."""
        all_results = self._suite.run_all()
        metrics = EvaluationMetrics()

        for category, results in all_results.items():
            verdicts = self._judge.judge_batch(results)
            cm = metrics.aggregate(category, results, verdicts)
            self._baseline[category] = cm.success_rate

        return dict(self._baseline)

    def run_regression(self) -> list[RegressionResult]:
        """Run the full suite and compare against stored baseline."""
        all_results = self._suite.run_all()
        metrics = EvaluationMetrics()
        regression_results: list[RegressionResult] = []

        for category, results in all_results.items():
            verdicts = self._judge.judge_batch(results)
            cm = metrics.aggregate(category, results, verdicts)

            baseline_rate = self._baseline.get(category, 0.0)
            delta = cm.success_rate - baseline_rate
            regressed = delta < -self._threshold

            regression_results.append(
                RegressionResult(
                    category=category,
                    baseline_success_rate=baseline_rate,
                    current_success_rate=cm.success_rate,
                    delta=round(delta, 4),
                    regressed=regressed,
                )
            )

        return regression_results

    def has_regressions(self) -> bool:
        """Convenience: run regression and return True if any category regressed."""
        return any(r.regressed for r in self.run_regression())

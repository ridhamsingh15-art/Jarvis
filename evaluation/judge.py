from dataclasses import dataclass

from .scenarios import ScenarioResult


@dataclass(frozen=True)
class Verdict:
    """Immutable judgment for a single scenario result."""

    case_id: str
    passed: bool
    quality_score: float
    reasoning: str


class EvaluationJudge:
    """Scores scenario results against expected outputs, computing pass/fail
    verdicts and quality scores."""

    def judge(self, result: ScenarioResult) -> Verdict:
        if result.success:
            quality = self._compute_quality(result)
            return Verdict(
                case_id=result.case_id,
                passed=True,
                quality_score=quality,
                reasoning="Output matched expected result",
            )

        return Verdict(
            case_id=result.case_id,
            passed=False,
            quality_score=0.0,
            reasoning=f"Expected match not found in: {result.actual_output[:100]}",
        )

    def judge_batch(self, results: list[ScenarioResult]) -> list[Verdict]:
        return [self.judge(r) for r in results]

    def _compute_quality(self, result: ScenarioResult) -> float:
        """Quality score based on latency and token efficiency. Range 0.0-1.0."""
        latency_score = max(0.0, 1.0 - (result.elapsed_ms / 5000.0))
        token_score = max(0.0, 1.0 - (result.token_count / 1000.0))
        return round((latency_score * 0.6 + token_score * 0.4), 4)

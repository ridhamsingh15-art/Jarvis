"""
Experience Evaluator.

Analyses a completed ExperienceRecord and scores individual stage outcomes
to detect patterns (repeated failures, slow stages, retry storms).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from .models import ExperienceRecord, StageOutcome

logger = logging.getLogger(__name__)

# Thresholds
_SLOW_STAGE_MS = 30_000      # 30 s
_RETRY_STORM_THRESHOLD = 3   # ≥3 retries on a single stage


@dataclass
class EvaluationResult:
    overall_score: float          # 0.0–1.0
    slow_stages: list[str]
    retry_storms: list[str]
    failed_stages: list[str]
    analytics_score: float        # 0.0–1.0; based on CTR + retention
    summary: str


class ExperienceEvaluator:
    """Scores an ExperienceRecord to identify what needs improvement."""

    def evaluate(self, record: ExperienceRecord) -> EvaluationResult:
        slow_stages: list[str] = []
        retry_storms: list[str] = []

        for outcome in record.stage_outcomes:
            if outcome.duration_ms > _SLOW_STAGE_MS:
                slow_stages.append(outcome.stage_id)
            if outcome.retries >= _RETRY_STORM_THRESHOLD:
                retry_storms.append(outcome.stage_id)

        # Success rate
        total = len(record.stage_outcomes)
        passed = sum(1 for o in record.stage_outcomes if o.success)
        success_rate = (passed / total) if total > 0 else 1.0

        # Analytics score (blended CTR + retention, 0–1)
        analytics_score = 0.5  # neutral default
        if record.analytics:
            a = record.analytics
            analytics_score = min(
                1.0,
                (a.ctr * 0.3 + a.retention * 0.4 + a.completion_rate * 0.3)
            )

        overall_score = (success_rate * 0.6 + analytics_score * 0.4)

        summary_parts = []
        if record.failed_stages:
            summary_parts.append(f"Failed stages: {', '.join(record.failed_stages)}.")
        if slow_stages:
            summary_parts.append(f"Slow stages: {', '.join(slow_stages)}.")
        if retry_storms:
            summary_parts.append(f"Retry storms: {', '.join(retry_storms)}.")
        if not summary_parts:
            summary_parts.append("All stages completed cleanly.")

        return EvaluationResult(
            overall_score=round(overall_score, 3),
            slow_stages=slow_stages,
            retry_storms=retry_storms,
            failed_stages=record.failed_stages,
            analytics_score=round(analytics_score, 3),
            summary=" ".join(summary_parts),
        )

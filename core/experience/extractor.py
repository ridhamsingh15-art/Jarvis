"""
Experience Extractor.

Converts completed mission data (Mission object + AgentResults + optional
analytics) into a structured ExperienceRecord ready for storage.
"""
from __future__ import annotations

import logging
import time
from typing import Any

from core.agents.models import AgentResult
from core.agents.enums import TaskState
from core.mission.models import Mission
from core.mission.enums import MissionStatus

from .models import (
    AnalyticsSnapshot,
    ExperienceRecord,
    ExperienceType,
    StageOutcome,
)

logger = logging.getLogger(__name__)


class ExperienceExtractor:
    """
    Extracts an ExperienceRecord from a completed mission and its agent results.
    """

    def extract(
        self,
        mission: Mission,
        agent_results: list[AgentResult],
        ordered_steps: list[str],
        analytics: AnalyticsSnapshot | None = None,
        user_feedback: str | None = None,
        user_rating: float | None = None,
    ) -> ExperienceRecord:
        """
        Build an ExperienceRecord from mission outcome data.
        """
        failed_stages: list[str] = []
        stage_outcomes: list[StageOutcome] = []
        total_retries = 0

        for step, result in zip(ordered_steps, agent_results):
            success = result.status == TaskState.COMPLETED
            error = result.metrics.get("error") if not success else None
            retries = int(result.metrics.get("retries", 0))
            total_retries += retries

            stage_outcomes.append(StageOutcome(
                stage_id=step,
                capability=step,
                success=success,
                duration_ms=float(result.metrics.get("duration_ms", 0)),
                retries=retries,
                error_summary=error,
                payload_keys=list(result.payload.keys()),
            ))

            if not success:
                failed_stages.append(step)

        overall_success = len(failed_stages) == 0
        exp_type = (
            ExperienceType.SUCCESSFUL_WORKFLOW if overall_success
            else ExperienceType.FAILED_WORKFLOW
        )

        # Extract topic/format from mission metadata
        topic = mission.metadata.get("topic", mission.title)
        fmt = mission.metadata.get("format", "video")

        record = ExperienceRecord(
            mission_id=mission.mission_id.value,
            mission_title=mission.title,
            experience_type=exp_type,
            topic=str(topic),
            format=str(fmt),
            ordered_steps=list(ordered_steps),
            stage_outcomes=stage_outcomes,
            overall_success=overall_success,
            failed_stages=failed_stages,
            retry_count=total_retries,
            analytics=analytics,
            user_feedback=user_feedback,
            user_rating=user_rating,
        )

        logger.info(
            f"Extracted experience {record.id} for mission '{mission.title}' "
            f"— success={overall_success}, failed_stages={failed_stages}"
        )
        return record

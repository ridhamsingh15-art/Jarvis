"""
Experience Manager — the facade for the entire Experience & Learning engine.

Usage::

    # After a mission completes
    experience_manager.record_mission(mission, agent_results, ordered_steps)

    # Before planning a new mission
    context = experience_manager.retrieve_context("Ramayana")
    prompt_block = context.format_for_prompt()
"""
from __future__ import annotations

import logging
from typing import Optional

from core.agents.models import AgentResult
from core.mission.models import Mission

from .evaluator import ExperienceEvaluator
from .exceptions import DuplicateExperienceError, ExtractionError
from .extractor import ExperienceExtractor
from .learner import ExperienceLearner
from .models import AnalyticsSnapshot, ExperienceRecord, Lesson
from .repository import InMemoryExperienceRepository
from .retrieval import ExperienceRetriever, RetrievalContext

logger = logging.getLogger(__name__)


class ExperienceManager:
    """
    Central façade for the Experience & Continuous Learning Engine.

    After every completed mission, call ``record_mission`` to extract,
    evaluate, and learn from the outcome. Before planning, call
    ``retrieve_context`` to surface relevant prior lessons.
    """

    def __init__(self, repository: InMemoryExperienceRepository) -> None:
        self._repo = repository
        self._extractor = ExperienceExtractor()
        self._evaluator = ExperienceEvaluator()
        self._learner = ExperienceLearner(self._evaluator, self._repo)
        self._retriever = ExperienceRetriever(self._repo)

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record_mission(
        self,
        mission: Mission,
        agent_results: list[AgentResult],
        ordered_steps: list[str],
        analytics: Optional[AnalyticsSnapshot] = None,
        user_feedback: Optional[str] = None,
        user_rating: Optional[float] = None,
    ) -> tuple[ExperienceRecord, list[Lesson]]:
        """
        Extract an ExperienceRecord from a completed mission, evaluate it,
        extract lessons, and persist everything.

        Returns the saved record and the list of new lessons generated.
        """
        # Guard: don't double-record the same mission
        existing = self._repo.find_records_by_mission(mission.mission_id.value)
        if existing:
            raise DuplicateExperienceError(
                f"Mission {mission.mission_id.value} already has an experience record."
            )

        try:
            record = self._extractor.extract(
                mission=mission,
                agent_results=agent_results,
                ordered_steps=ordered_steps,
                analytics=analytics,
                user_feedback=user_feedback,
                user_rating=user_rating,
            )
        except Exception as e:
            raise ExtractionError(f"Failed to extract experience: {e}") from e

        self._repo.save_record(record)

        # Learn from the record
        lessons = self._learner.learn(record)

        logger.info(
            f"Experience recorded: {record.id} — "
            f"success={record.overall_success}, lessons={len(lessons)}"
        )
        return record, lessons

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    def retrieve_context(self, topic: str) -> RetrievalContext:
        """
        Retrieve relevant prior experience for a topic, ready to be injected
        into the Executive Brain's planning context.
        """
        return self._retriever.retrieve(topic)

    # ------------------------------------------------------------------
    # Direct access
    # ------------------------------------------------------------------

    def list_records(self) -> list[ExperienceRecord]:
        return self._repo.list_records()

    def list_lessons(self) -> list[Lesson]:
        return self._repo.list_lessons()

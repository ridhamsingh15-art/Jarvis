"""
Experience Learner.

Distils ExperienceRecords (via EvaluationResults) into reusable Lessons.
Lessons are stored back in the repository and retrieved by the Executive
Brain before planning future missions.
"""
from __future__ import annotations

import logging
import uuid
from typing import Optional

from .evaluator import EvaluationResult, ExperienceEvaluator
from .models import ExperienceRecord, Lesson, LessonCategory
from .repository import InMemoryExperienceRepository

logger = logging.getLogger(__name__)

# How much to decay an existing lesson's confidence when contradicted
_CONTRADICTION_DECAY = 0.15


class ExperienceLearner:
    """
    Extracts reusable Lessons from EvaluationResults and manages their
    lifecycle (creation, contradiction detection, confidence decay).
    """

    def __init__(
        self,
        evaluator: ExperienceEvaluator,
        repository: InMemoryExperienceRepository,
    ) -> None:
        self._evaluator = evaluator
        self._repo = repository

    def learn(self, record: ExperienceRecord) -> list[Lesson]:
        """
        Evaluate a record and emit zero or more Lessons, persisting them
        to the repository. Returns the new lessons created.
        """
        evaluation = self._evaluator.evaluate(record)
        lessons: list[Lesson] = []

        # --- Lesson: failed stages → try a different tool/agent ---
        for stage in evaluation.failed_stages:
            lesson = self._make_lesson(
                category=LessonCategory.TOOLING,
                topic=record.topic,
                summary=f"Stage '{stage}' failed during {record.topic} production.",
                recommendation=f"Consider a fallback agent or skip '{stage}' if non-critical.",
                source_id=record.id,
            )
            lessons.append(lesson)

        # --- Lesson: retry storms → add back-off or pre-check ---
        for stage in evaluation.retry_storms:
            lesson = self._make_lesson(
                category=LessonCategory.RETRY_PATTERN,
                topic=record.topic,
                summary=f"Stage '{stage}' required ≥3 retries in {record.topic} production.",
                recommendation=f"Add exponential back-off or a pre-validation step before '{stage}'.",
                source_id=record.id,
            )
            lessons.append(lesson)

        # --- Lesson: slow stages → parallelise or cache ---
        for stage in evaluation.slow_stages:
            lesson = self._make_lesson(
                category=LessonCategory.TIMING,
                topic=record.topic,
                summary=f"Stage '{stage}' was slow (>30s) in {record.topic} production.",
                recommendation=f"Consider parallelising or pre-computing '{stage}' outputs.",
                source_id=record.id,
            )
            lessons.append(lesson)

        # --- Lesson: low analytics → adjust content strategy ---
        if record.analytics and evaluation.analytics_score < 0.4:
            lesson = self._make_lesson(
                category=LessonCategory.ANALYTICS,
                topic=record.topic,
                summary=(
                    f"Low engagement (score={evaluation.analytics_score:.2f}) "
                    f"for {record.topic} content."
                ),
                recommendation=(
                    "Experiment with shorter intros, stronger hooks, or different thumbnails."
                ),
                source_id=record.id,
                confidence=0.7,
            )
            lessons.append(lesson)

        # --- Lesson: user feedback (positive preference) ---
        if record.user_feedback and record.user_rating and record.user_rating >= 4.0:
            lesson = self._make_lesson(
                category=LessonCategory.USER_FEEDBACK,
                topic=record.topic,
                summary=f"User rated {record.topic} highly ({record.user_rating}/5).",
                recommendation=f"Replicate the workflow steps used for '{record.topic}'.",
                source_id=record.id,
                confidence=0.9,
            )
            lessons.append(lesson)

        # Persist and handle contradictions
        for lesson in lessons:
            self._resolve_contradictions(lesson)
            self._repo.save_lesson(lesson)
            logger.info(f"Lesson stored: [{lesson.category}] {lesson.summary}")

        return lessons

    def _make_lesson(
        self,
        category: LessonCategory,
        topic: str,
        summary: str,
        recommendation: str,
        source_id: str,
        confidence: float = 1.0,
    ) -> Lesson:
        return Lesson(
            id=f"lesson_{uuid.uuid4().hex[:10]}",
            category=category,
            topic=topic,
            summary=summary,
            recommendation=recommendation,
            confidence=confidence,
            source_experience_ids=[source_id],
        )

    def _resolve_contradictions(self, new_lesson: Lesson) -> None:
        """
        If an existing lesson with the same topic + category exists but the
        new lesson has opposite polarity (e.g., one says a stage succeeds,
        another says it fails), decay the older one's confidence.
        """
        existing = [
            l for l in self._repo.list_lessons()
            if l.topic == new_lesson.topic and l.category == new_lesson.category
        ]
        for old in existing:
            if old.summary != new_lesson.summary:
                # Decay existing lesson — replace with reduced-confidence copy
                decayed = Lesson(
                    id=old.id,
                    category=old.category,
                    topic=old.topic,
                    summary=old.summary,
                    recommendation=old.recommendation,
                    confidence=max(0.0, old.confidence - _CONTRADICTION_DECAY),
                    source_experience_ids=old.source_experience_ids,
                    created_at=old.created_at,
                )
                self._repo.save_lesson(decayed)
                logger.debug(f"Decayed contradictory lesson {old.id} to confidence={decayed.confidence:.2f}")

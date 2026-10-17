"""
Experience Retrieval.

Provides the Executive Brain with relevant prior lessons and experience
records before it begins planning a new mission.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from .models import ExperienceRecord, Lesson
from .repository import InMemoryExperienceRepository

logger = logging.getLogger(__name__)

# Minimum confidence to surface a lesson to the planner
_MIN_CONFIDENCE = 0.4

# Max lessons to inject per planning session to avoid context bloat
_MAX_LESSONS = 5
_MAX_RECORDS = 3


@dataclass
class RetrievalContext:
    """Package of prior experience passed to the Executive Brain."""
    topic: str
    relevant_records: list[ExperienceRecord]
    applicable_lessons: list[Lesson]

    def format_for_prompt(self) -> str:
        """Serialises this context into a plain-text block for LLM injection."""
        lines: list[str] = [f"## Prior Experience for topic: {self.topic}"]

        if self.relevant_records:
            lines.append("\n### Recent Executions")
            for r in self.relevant_records:
                status = "✓" if r.overall_success else "✗"
                lines.append(
                    f"  {status} [{r.experience_type}] '{r.mission_title}' "
                    f"— failed stages: {r.failed_stages or 'none'}"
                )
        else:
            lines.append("\n_No prior executions found for this topic._")

        if self.applicable_lessons:
            lines.append("\n### Learned Lessons")
            for lesson in self.applicable_lessons:
                lines.append(
                    f"  [{lesson.category}] {lesson.summary}\n"
                    f"    → Recommendation: {lesson.recommendation}"
                )
        else:
            lines.append("\n_No lessons available yet._")

        return "\n".join(lines)


class ExperienceRetriever:
    """
    Retrieves relevant ExperienceRecords and Lessons from the repository,
    ranked by topic similarity and lesson confidence.
    """

    def __init__(self, repository: InMemoryExperienceRepository) -> None:
        self._repo = repository

    def retrieve(self, topic: str) -> RetrievalContext:
        """
        Fetch the most relevant prior experiences and lessons for a given topic.
        """
        # Records
        records = self._repo.find_records_by_topic(topic)
        # Sort by recency (created_at is an ISO string — lexicographic sort is safe)
        records.sort(key=lambda r: r.created_at, reverse=True)
        records = records[:_MAX_RECORDS]

        # Lessons — filter by confidence threshold, rank by confidence desc
        lessons = [
            l for l in self._repo.find_lessons_by_topic(topic)
            if l.confidence >= _MIN_CONFIDENCE
        ]
        lessons.sort(key=lambda l: l.confidence, reverse=True)
        lessons = lessons[:_MAX_LESSONS]

        logger.info(
            f"Retrieved {len(records)} records and {len(lessons)} lessons "
            f"for topic='{topic}'"
        )

        return RetrievalContext(
            topic=topic,
            relevant_records=records,
            applicable_lessons=lessons,
        )

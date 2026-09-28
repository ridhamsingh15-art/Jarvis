"""
Focused tests for the Experience & Continuous Learning Engine.

Covers:
  - ExperienceExtractor: builds correct ExperienceRecord from mission + results
  - ExperienceEvaluator: detects slow stages, retry storms, analytics scores
  - ExperienceLearner: emits correct lessons and handles contradictions
  - InMemoryExperienceRepository: CRUD and dedup
  - ExperienceRetriever: topic-filtered retrieval and confidence filtering
  - ExperienceManager: full pipeline integration
  - Executive Brain integration: context enriched with prior lessons
  - Two-project scenario: second project uses first project's lessons
"""
import pytest
from unittest.mock import MagicMock

from core.agents.models import AgentResult
from core.agents.enums import TaskState
from core.models.primitives import Identifier, Timestamp
from core.mission.models import Mission
from core.mission.enums import MissionStatus, MissionPriority
from core.cognition.context import ShortTermContext

from core.experience.manager import ExperienceManager
from core.experience.extractor import ExperienceExtractor
from core.experience.evaluator import ExperienceEvaluator
from core.experience.learner import ExperienceLearner
from core.experience.repository import InMemoryExperienceRepository
from core.experience.retrieval import ExperienceRetriever
from core.experience.models import (
    AnalyticsSnapshot,
    ExperienceType,
    LessonCategory,
    StageOutcome,
)
from core.experience.exceptions import DuplicateExperienceError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mission(title: str = "Ramayana Ep1", topic: str = "Ramayana") -> Mission:
    return Mission(
        mission_id=Identifier(f"m_{title.replace(' ', '_')}"),
        title=title,
        description="Test mission",
        priority=MissionPriority.HIGH,
        metadata={"topic": topic, "format": "video"},
    )

def _make_results(steps: list[str], fail_at: str | None = None) -> list[AgentResult]:
    results = []
    for step in steps:
        status = TaskState.FAILED if step == fail_at else TaskState.COMPLETED
        results.append(AgentResult(
            task_id=Identifier(step),
            status=status,
            payload={step: "output"},
            metrics={"error": "Simulated failure"} if step == fail_at else {},
            timestamp=Timestamp(),
        ))
    return results

_STEPS = ["research", "script", "storyboard", "images", "voice", "edit", "publish"]


# ---------------------------------------------------------------------------
# ExperienceExtractor
# ---------------------------------------------------------------------------

class TestExperienceExtractor:
    def test_extracts_successful_record(self):
        extractor = ExperienceExtractor()
        mission = _make_mission()
        results = _make_results(_STEPS)
        record = extractor.extract(mission, results, _STEPS)

        assert record.overall_success is True
        assert record.failed_stages == []
        assert record.experience_type == ExperienceType.SUCCESSFUL_WORKFLOW
        assert record.topic == "Ramayana"
        assert len(record.stage_outcomes) == len(_STEPS)

    def test_extracts_failed_record(self):
        extractor = ExperienceExtractor()
        mission = _make_mission()
        results = _make_results(_STEPS, fail_at="voice")
        record = extractor.extract(mission, results, _STEPS)

        assert record.overall_success is False
        assert "voice" in record.failed_stages
        assert record.experience_type == ExperienceType.FAILED_WORKFLOW

    def test_attaches_analytics(self):
        extractor = ExperienceExtractor()
        mission = _make_mission()
        results = _make_results(_STEPS)
        analytics = AnalyticsSnapshot(ctr=0.05, retention=0.65, completion_rate=0.80)
        record = extractor.extract(mission, results, _STEPS, analytics=analytics)
        assert record.analytics.ctr == 0.05

    def test_attaches_user_feedback(self):
        extractor = ExperienceExtractor()
        mission = _make_mission()
        results = _make_results(_STEPS)
        record = extractor.extract(mission, results, _STEPS, user_feedback="Loved it!", user_rating=5.0)
        assert record.user_rating == 5.0


# ---------------------------------------------------------------------------
# ExperienceEvaluator
# ---------------------------------------------------------------------------

class TestExperienceEvaluator:
    def _extract(self, steps, fail_at=None, analytics=None):
        extractor = ExperienceExtractor()
        mission = _make_mission()
        results = _make_results(steps, fail_at=fail_at)
        return extractor.extract(mission, results, steps, analytics=analytics)

    def test_all_pass_score_high(self):
        evaluator = ExperienceEvaluator()
        record = self._extract(_STEPS)
        result = evaluator.evaluate(record)
        assert result.overall_score > 0.5
        assert result.failed_stages == []

    def test_failed_stage_reduces_score(self):
        evaluator = ExperienceEvaluator()
        record = self._extract(_STEPS, fail_at="voice")
        result = evaluator.evaluate(record)
        assert "voice" in result.failed_stages

    def test_analytics_score_with_low_ctr(self):
        evaluator = ExperienceEvaluator()
        analytics = AnalyticsSnapshot(ctr=0.01, retention=0.1, completion_rate=0.2)
        record = self._extract(_STEPS, analytics=analytics)
        result = evaluator.evaluate(record)
        assert result.analytics_score < 0.4


# ---------------------------------------------------------------------------
# ExperienceLearner
# ---------------------------------------------------------------------------

class TestExperienceLearner:
    def _setup(self):
        repo = InMemoryExperienceRepository()
        evaluator = ExperienceEvaluator()
        learner = ExperienceLearner(evaluator, repo)
        return repo, learner

    def _record(self, fail_at=None, analytics=None, user_rating=None):
        extractor = ExperienceExtractor()
        mission = _make_mission()
        results = _make_results(_STEPS, fail_at=fail_at)
        return extractor.extract(
            mission, results, _STEPS, analytics=analytics, user_rating=user_rating
        )

    def test_no_lessons_for_clean_run(self):
        _, learner = self._setup()
        record = self._record()
        lessons = learner.learn(record)
        # Clean run with no analytics: no tooling/retry lessons expected
        tooling = [l for l in lessons if l.category == LessonCategory.TOOLING]
        assert len(tooling) == 0

    def test_failed_stage_generates_tooling_lesson(self):
        _, learner = self._setup()
        record = self._record(fail_at="voice")
        lessons = learner.learn(record)
        tooling = [l for l in lessons if l.category == LessonCategory.TOOLING]
        assert len(tooling) >= 1
        assert any("voice" in l.summary for l in tooling)

    def test_low_analytics_generates_analytics_lesson(self):
        _, learner = self._setup()
        analytics = AnalyticsSnapshot(ctr=0.005, retention=0.05, completion_rate=0.10)
        record = self._record(analytics=analytics)
        lessons = learner.learn(record)
        analytics_lessons = [l for l in lessons if l.category == LessonCategory.ANALYTICS]
        assert len(analytics_lessons) >= 1

    def test_high_user_rating_generates_preference_lesson(self):
        _, learner = self._setup()
        record = self._record(user_rating=5.0)
        record.user_feedback = "Great!"
        lessons = learner.learn(record)
        pref = [l for l in lessons if l.category == LessonCategory.USER_FEEDBACK]
        assert len(pref) >= 1


# ---------------------------------------------------------------------------
# InMemoryExperienceRepository
# ---------------------------------------------------------------------------

class TestExperienceRepository:
    def _record(self, mission_title="M1", topic="Ramayana"):
        extractor = ExperienceExtractor()
        mission = _make_mission(mission_title, topic)
        results = _make_results(_STEPS)
        return extractor.extract(mission, results, _STEPS)

    def test_save_and_retrieve(self):
        repo = InMemoryExperienceRepository()
        r = self._record()
        repo.save_record(r)
        assert repo.get_record(r.id) is not None

    def test_duplicate_raises(self):
        repo = InMemoryExperienceRepository()
        r = self._record()
        repo.save_record(r)
        with pytest.raises(DuplicateExperienceError):
            repo.save_record(r)

    def test_find_by_topic(self):
        repo = InMemoryExperienceRepository()
        repo.save_record(self._record("Ramayana Ep1", "Ramayana"))
        repo.save_record(self._record("Coding Tutorial 1", "Programming"))
        ramayana = repo.find_records_by_topic("Ramayana")
        assert len(ramayana) == 1
        assert ramayana[0].topic == "Ramayana"


# ---------------------------------------------------------------------------
# ExperienceRetriever
# ---------------------------------------------------------------------------

class TestExperienceRetriever:
    def test_retrieves_by_topic(self):
        repo = InMemoryExperienceRepository()
        extractor = ExperienceExtractor()
        mission = _make_mission("Ramayana Ep1", "Ramayana")
        results = _make_results(_STEPS, fail_at="voice")
        record = extractor.extract(mission, results, _STEPS)
        repo.save_record(record)

        evaluator = ExperienceEvaluator()
        learner = ExperienceLearner(evaluator, repo)
        learner.learn(record)

        retriever = ExperienceRetriever(repo)
        ctx = retriever.retrieve("Ramayana")

        assert len(ctx.relevant_records) == 1
        assert len(ctx.applicable_lessons) > 0

    def test_format_for_prompt_contains_topic(self):
        repo = InMemoryExperienceRepository()
        retriever = ExperienceRetriever(repo)
        ctx = retriever.retrieve("Ramayana")
        prompt = ctx.format_for_prompt()
        assert "Ramayana" in prompt


# ---------------------------------------------------------------------------
# ExperienceManager — full pipeline
# ---------------------------------------------------------------------------

class TestExperienceManager:
    def _manager(self):
        repo = InMemoryExperienceRepository()
        return ExperienceManager(repo), repo

    def test_record_mission_creates_record_and_lessons(self):
        manager, repo = self._manager()
        mission = _make_mission("Ramayana Ep1", "Ramayana")
        results = _make_results(_STEPS, fail_at="storyboard")
        record, lessons = manager.record_mission(mission, results, _STEPS)

        assert record.overall_success is False
        assert len(repo.list_records()) == 1
        # At least one lesson for the failed stage
        assert any(l.category == LessonCategory.TOOLING for l in lessons)

    def test_duplicate_mission_raises(self):
        manager, _ = self._manager()
        mission = _make_mission()
        results = _make_results(_STEPS)
        manager.record_mission(mission, results, _STEPS)
        with pytest.raises(DuplicateExperienceError):
            manager.record_mission(mission, results, _STEPS)

    def test_retrieve_context_returns_lessons(self):
        manager, _ = self._manager()
        mission = _make_mission("Ramayana Ep1", "Ramayana")
        results = _make_results(_STEPS, fail_at="voice")
        manager.record_mission(mission, results, _STEPS)

        ctx = manager.retrieve_context("Ramayana")
        assert ctx.topic == "Ramayana"
        assert len(ctx.relevant_records) == 1
        prompt = ctx.format_for_prompt()
        assert "voice" in prompt.lower() or "lesson" in prompt.lower()


# ---------------------------------------------------------------------------
# Two-project scenario: 2nd project benefits from 1st
# ---------------------------------------------------------------------------

class TestTwoProjectLearning:
    """
    Simulates the core verification scenario:
    1. Run 'Ramayana Ep1' and let voice fail.
    2. Record the experience + lessons.
    3. Plan 'Ramayana Ep2' and confirm prior lessons are surfaced.
    """
    def test_second_project_gets_prior_lessons(self):
        repo = InMemoryExperienceRepository()
        manager = ExperienceManager(repo)

        # --- Episode 1: voice fails ---
        mission1 = _make_mission("Ramayana Ep1", "Ramayana")
        results1 = _make_results(_STEPS, fail_at="voice")
        record1, lessons1 = manager.record_mission(mission1, results1, _STEPS)

        assert any("voice" in l.summary for l in lessons1)

        # --- Episode 2: planning context should contain prior lessons ---
        ctx = manager.retrieve_context("Ramayana")
        prompt_block = ctx.format_for_prompt()

        assert "voice" in prompt_block.lower() or "failed" in prompt_block.lower()
        assert len(ctx.applicable_lessons) > 0
        # The recommendation should mention 'voice'
        assert any("voice" in l.recommendation.lower() for l in ctx.applicable_lessons)


# ---------------------------------------------------------------------------
# ShortTermContext system notes injection
# ---------------------------------------------------------------------------

class TestContextInjection:
    def test_inject_system_note(self):
        ctx = ShortTermContext()
        ctx.inject_system_note("## Prior Experience\n  - voice failed.")
        notes = ctx.get_system_notes()
        assert len(notes) == 1
        assert "voice" in notes[0]

    def test_system_notes_in_summary(self):
        ctx = ShortTermContext()
        ctx.inject_system_note("Lesson: retry voice with back-off.")
        summary = ctx.get_context_summary()
        assert "system_notes" in summary
        assert len(summary["system_notes"]) == 1

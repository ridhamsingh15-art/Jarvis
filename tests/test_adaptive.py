from unittest.mock import MagicMock

import pytest

from core.adaptive import (
    AdaptiveLearningManager,
    DefaultExperienceCollector,
    DeterministicPatternDetector,
    Experience,
    InMemoryExperienceRepository,
    LearningDecision,
    LearningPattern,
    LearningPolicy,
    MetricsEvaluator,
    PatternType,
    PlanOptimizer,
    RuleBasedLearner,
)
from core.events.bus import EventBus
from core.models.primitives import Identifier
from core.runtime.enums import ComponentState, HealthState


@pytest.fixture
def repository():
    return InMemoryExperienceRepository()


@pytest.fixture
def collector():
    return DefaultExperienceCollector()


@pytest.fixture
def detector():
    return DeterministicPatternDetector()


@pytest.fixture
def policy():
    return LearningPolicy(minimum_repetitions=2, minimum_confidence=0.5, minimum_success_rate=0.6)


@pytest.fixture
def learner(policy):
    return RuleBasedLearner(policy)


@pytest.fixture
def evaluator():
    return MetricsEvaluator()


@pytest.fixture
def optimizer():
    return PlanOptimizer()


@pytest.fixture
def event_bus():
    logger = MagicMock()
    return EventBus(logger)


@pytest.fixture
def manager(repository, collector, detector, learner, evaluator, optimizer, event_bus):
    logger = MagicMock()
    return AdaptiveLearningManager(
        repository, collector, detector, learner, evaluator, optimizer, event_bus, logger
    )


def test_experience_repository(repository):
    e1 = Experience(user_input="test 1", success=True, duration=1.0, skill_id=Identifier("s1"))
    e2 = Experience(user_input="test 2", success=False, duration=2.0, workflow_id=Identifier("w1"))
    
    repository.save(e1)
    repository.save(e2)
    
    assert len(repository.list()) == 2
    assert repository.get(e1.id) == e1
    
    skill_exps = repository.find_by_skill(Identifier("s1"))
    assert len(skill_exps) == 1
    
    workflow_exps = repository.find_by_workflow(Identifier("w1"))
    assert len(workflow_exps) == 1
    
    assert len(repository.find_successful()) == 1
    assert len(repository.find_failed()) == 1
    
    stats = repository.statistics()
    assert stats["total_experiences"] == 2
    assert stats["success_rate"] == 0.5
    
    repository.remove(e1.id)
    assert len(repository.list()) == 1


def test_experience_collector(collector):
    exp = collector.record_mission(
        user_input="hello", 
        success=True, 
        duration=1.5,
        skill_id="s1",
        workflow_id="w1",
        tasks=["t1", "t2"],
        metadata={"foo": "bar"}
    )
    assert exp.user_input == "hello"
    assert exp.success is True
    assert exp.skill_id.value == "s1"
    assert exp.workflow_id.value == "w1"
    assert exp.tasks == ["t1", "t2"]
    assert exp.metadata.annotations.get("foo") == "bar"


def test_pattern_detection(detector):
    e1 = Experience(user_input="t", success=True, duration=1.0, skill_id=Identifier("s1"), tasks=["a", "b"])
    e2 = Experience(user_input="t", success=True, duration=1.2, skill_id=Identifier("s1"), tasks=["a", "b"])
    
    patterns = detector.detect([e1, e2])
    
    # Expect 1 SKILL pattern and 1 TASK_SEQUENCE pattern
    assert len(patterns) == 2
    types = [p.pattern_type for p in patterns]
    assert PatternType.SKILL in types
    assert PatternType.TASK_SEQUENCE in types
    assert all(p.confidence == 1.0 for p in patterns)
    assert all(p.occurrences == 2 for p in patterns)


def test_learner(learner):
    # Based on policy: min_reps=2, min_success_rate=0.6
    p1 = LearningPattern(pattern_type=PatternType.SKILL, occurrences=3, confidence=0.1, source_experiences=[])
    p2 = LearningPattern(pattern_type=PatternType.WORKFLOW, occurrences=3, confidence=0.9, source_experiences=[])
    p3 = LearningPattern(pattern_type=PatternType.TASK_SEQUENCE, occurrences=1, confidence=1.0, source_experiences=[]) # below reps
    
    recs = learner.learn([p1, p2, p3])
    
    assert len(recs) == 3
    # p1: skill failing -> OPTIMIZE
    assert recs[0].decision == LearningDecision.OPTIMIZE_SKILL
    # p2: workflow successful -> CREATE_SKILL
    assert recs[1].decision == LearningDecision.CREATE_SKILL
    # p3: below reps -> IGNORE
    assert recs[2].decision == LearningDecision.IGNORE


def test_evaluator(evaluator):
    e1 = Experience(user_input="1", success=True, duration=1.0)
    e2 = Experience(user_input="2", success=False, duration=3.0)
    e3 = Experience(user_input="3", success=True, duration=2.0)
    
    metrics = evaluator.evaluate([e1, e2, e3])
    assert metrics["execution_count"] == 3
    assert metrics["success_rate"] == 2 / 3
    assert metrics["average_duration"] == 2.0
    assert metrics["median_duration"] == 2.0


def test_optimizer(optimizer):
    from core.adaptive.models import LearningRecommendation
    from core.models.primitives import Identifier
    
    r1 = LearningRecommendation(decision=LearningDecision.CREATE_SKILL, reason="test", confidence=1.0)
    r2 = LearningRecommendation(decision=LearningDecision.OPTIMIZE_SKILL, reason="test", confidence=0.5, target_skill=Identifier("s1"))
    r3 = LearningRecommendation(decision=LearningDecision.IGNORE, reason="test", confidence=0.1)
    
    plan = optimizer.optimize([r1, r2, r3])
    
    assert len(plan.planner_hints) == 1
    assert plan.skill_confidence_adjustments["s1"] == -0.2


@pytest.mark.asyncio
async def test_manager_lifecycle(manager):
    assert manager.state == ComponentState.INITIALIZED
    
    await manager.start()
    assert manager.state == ComponentState.RUNNING
    
    health = await manager.health()
    assert health.state == HealthState.HEALTHY
    
    await manager.stop()
    assert manager.state == ComponentState.STOPPED


def test_manager_operations(manager):
    # record
    exp = manager.record_experience("test", True, 1.0, skill_id="s1")
    assert exp is not None
    
    # second exp to form a pattern
    manager.record_experience("test2", True, 1.2, skill_id="s1")
    
    patterns = manager.analyze()
    assert len(patterns) > 0
    
    recs = manager.learn(patterns)
    # The default policy in tests for learner isn't passed to manager, manager uses default Policy if any
    # Wait, the manager uses the injected learner.
    # The fixture for learner uses the mock policy.
    assert len(recs) == len(patterns)
    
    plan = manager.optimize(recs)
    assert plan is not None
    
    stats = manager.statistics()
    assert stats["total_experiences"] == 2

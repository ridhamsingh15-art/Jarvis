from unittest.mock import MagicMock

import pytest

from core.events.bus import EventBus
from core.improvement import (
    DefaultBehaviorOptimizer,
    DefaultImprovementRecommender,
    DefaultMetricsAggregator,
    DefaultSystemAnalyzer,
    DefaultTrendEvaluator,
    InMemoryImprovementPersistence,
    MetricType,
    OptimizationCategory,
    OptimizationRecommendation,
    PolicyAction,
    SafetyPolicyEngine,
    SelfImprovementManager,
    SystemMetric,
)
from core.models.primitives import Identifier
from core.runtime.enums import ComponentState


@pytest.fixture
def manager():
    logger = MagicMock()
    event_bus = EventBus(logger)
    return SelfImprovementManager(
        aggregator=DefaultMetricsAggregator(),
        analyzer=DefaultSystemAnalyzer(),
        optimizer=DefaultBehaviorOptimizer(),
        recommender=DefaultImprovementRecommender(),
        evaluator=DefaultTrendEvaluator(),
        policy_engine=SafetyPolicyEngine(),
        persistence=InMemoryImprovementPersistence(),
        event_bus=event_bus,
        logger=logger
    )

def test_policy_engine():
    engine = SafetyPolicyEngine()
    
    # Safe
    rec1 = OptimizationRecommendation(
        id=Identifier("r1"),
        category=OptimizationCategory.PROVIDER_PRIORITY,
        target="openai",
        suggested_value=1.0,
        rationale="test"
    )
    assert engine.evaluate_recommendation(rec1, []) == PolicyAction.ALLOW
    
    # Unsafe negative weight
    rec_unsafe = OptimizationRecommendation(
        id=Identifier("r2"),
        category=OptimizationCategory.PROVIDER_PRIORITY,
        target="openai",
        suggested_value=-1.0,
        rationale="test"
    )
    assert engine.evaluate_recommendation(rec_unsafe, []) == PolicyAction.BLOCK_UNSAFE
    
    # Oscillation
    assert engine.evaluate_recommendation(rec1, [rec1]) == PolicyAction.BLOCK_OSCILLATION

@pytest.mark.asyncio
async def test_manager_lifecycle(manager):
    assert manager.state == ComponentState.INITIALIZED
    await manager.start()
    assert manager.state == ComponentState.RUNNING
    await manager.stop()
    assert manager.state == ComponentState.STOPPED

def test_metrics_analysis_loop(manager):
    # Track metrics
    manager.track_metric(SystemMetric(id=Identifier("m1"), type=MetricType.LATENCY, value=5000.0, context={"provider_id": "gemini"}))
    manager.track_metric(SystemMetric(id=Identifier("m2"), type=MetricType.TASK_SUCCESS, value=1.0))
    
    # Trigger analysis pipeline
    manager.analyze()
    
    history = manager.history()
    assert len(history) == 1
    report = history[0]
    
    # Should have a recommendation to downweight gemini due to high latency > 1000
    assert len(report.recommendations) == 1
    rec = report.recommendations[0]
    assert rec.category == OptimizationCategory.PROVIDER_PRIORITY
    assert rec.target == "gemini"
    assert rec.suggested_value == 0.5
    
    # Track again (within 60 seconds)
    manager.track_metric(SystemMetric(id=Identifier("m3"), type=MetricType.LATENCY, value=5000.0, context={"provider_id": "gemini"}))
    manager.analyze()
    
    # Rec should be blocked due to oscillation policy
    history2 = manager.history()
    assert len(history2) == 2
    report2 = history2[1]
    assert len(report2.recommendations) == 0

def test_trend_evaluator():
    evaluator = DefaultTrendEvaluator()
    from core.improvement import MetricSnapshot
    
    snap1 = MetricSnapshot(id=Identifier("s1"), metrics=[
        SystemMetric(id=Identifier("m1"), type=MetricType.TASK_SUCCESS, value=0.5)
    ])
    
    snap2 = MetricSnapshot(id=Identifier("s2"), metrics=[
        SystemMetric(id=Identifier("m2"), type=MetricType.TASK_SUCCESS, value=0.8)
    ])
    
    trends = evaluator.evaluate(snap2, [snap1])
    assert len(trends) == 1
    assert trends[0].metric_type == MetricType.TASK_SUCCESS
    from core.improvement import TrendDirection
    assert trends[0].direction == TrendDirection.IMPROVING

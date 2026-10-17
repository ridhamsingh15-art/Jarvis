from typing import Any

from core.events.bus import EventBus
from core.models.domain import Event
from core.runtime.enums import ComponentState, HealthState
from core.runtime.interfaces import RuntimeComponent
from core.runtime.models import ComponentMetadata, HealthReport
from core.telemetry import AsyncLogger

from .interfaces import (
    Evaluator,
    ExperienceCollector,
    ExperienceRepository,
    Learner,
    Optimizer,
    PatternDetector,
)
from .models import (
    Experience,
    LearningPattern,
    LearningRecommendation,
    OptimizationPlan,
)


class AdaptiveLearningManager(RuntimeComponent):
    """
    Orchestrates the Adaptive Learning subsystem.
    """

    def __init__(
        self,
        repository: ExperienceRepository,
        collector: ExperienceCollector,
        detector: PatternDetector,
        learner: Learner,
        evaluator: Evaluator,
        optimizer: Optimizer,
        event_bus: EventBus,
        logger: AsyncLogger
    ) -> None:
        self._repository = repository
        self._collector = collector
        self._detector = detector
        self._learner = learner
        self._evaluator = evaluator
        self._optimizer = optimizer
        self._event_bus = event_bus
        self._logger = logger
        
        self._state = ComponentState.INITIALIZED
        self._metadata = ComponentMetadata(
            id="core.adaptive",
            name="Adaptive Learning System",
            version="1.0.0",
            dependencies=["core.events", "core.telemetry"]
        )

    @property
    def metadata(self) -> ComponentMetadata:
        return self._metadata

    @property
    def state(self) -> ComponentState:
        return self._state

    async def start(self) -> None:
        if self._state in (ComponentState.STARTING, ComponentState.RUNNING):
            return
            
        self._state = ComponentState.STARTING
        self._logger.info("Starting Adaptive Learning System...")
        
        self._state = ComponentState.RUNNING
        self._logger.info("Adaptive Learning System started successfully.")

    async def stop(self) -> None:
        if self._state != ComponentState.RUNNING:
            return
            
        self._state = ComponentState.STOPPING
        self._logger.info("Stopping Adaptive Learning System...")
        
        self._state = ComponentState.STOPPED
        self._logger.info("Adaptive Learning System stopped.")

    async def health(self) -> HealthReport:
        try:
            stats = self._repository.statistics()
            return HealthReport(
                component_id=self.metadata.id,
                state=HealthState.HEALTHY,
                details=stats
            )
        except Exception as e:  # noqa: BLE001
            return HealthReport(
                component_id=self.metadata.id,
                state=HealthState.UNHEALTHY,
                error=str(e)
            )

    def record_experience(self, user_input: str, success: bool, duration: float, **kwargs: Any) -> Experience:
        """Record an execution experience and trigger asynchronous analysis."""
        experience = self._collector.record_mission(user_input, success, duration, **kwargs)
        self._repository.save(experience)
        
        event = Event(
            topic="adaptive.experience.recorded",
            payload={"experience_id": experience.id.value, "success": success},
            source=self.metadata.id
        )
        self._event_bus.publish(event)
        return experience

    def analyze(self) -> list[LearningPattern]:
        """Detect patterns from stored experiences."""
        experiences = self._repository.list()
        patterns = self._detector.detect(experiences)
        
        if patterns:
            event = Event(
                topic="adaptive.pattern.detected",
                payload={"patterns_count": len(patterns)},
                source=self.metadata.id
            )
            self._event_bus.publish(event)
            
        return patterns

    def learn(self, patterns: list[LearningPattern]) -> list[LearningRecommendation]:
        """Generate recommendations based on detected patterns."""
        recommendations = self._learner.learn(patterns)
        
        if recommendations:
            event = Event(
                topic="adaptive.learning.completed",
                payload={"recommendations_count": len(recommendations)},
                source=self.metadata.id
            )
            self._event_bus.publish(event)
            
        return recommendations

    def optimize(self, recommendations: list[LearningRecommendation]) -> OptimizationPlan:
        """Create an optimization plan based on learning recommendations."""
        plan = self._optimizer.optimize(recommendations)
        
        event = Event(
            topic="adaptive.optimized",
            payload={
                "adjustments_count": len(plan.skill_confidence_adjustments),
                "hints_count": len(plan.planner_hints)
            },
            source=self.metadata.id
        )
        self._event_bus.publish(event)
        return plan

    def statistics(self) -> dict[str, Any]:
        """Return system learning statistics."""
        return self._repository.statistics()

import builtins
import threading

from core.events.bus import EventBus
from core.models.domain import Event
from core.runtime.enums import ComponentState, HealthState
from core.runtime.interfaces import RuntimeComponent
from core.runtime.models import ComponentMetadata, HealthReport
from core.telemetry import AsyncLogger

from .enums import PolicyAction
from .exceptions import AnalysisError
from .interfaces import (
    IBehaviorOptimizer,
    IImprovementPersistence,
    IImprovementRecommender,
    IMetricsAggregator,
    IPolicyEngine,
    ISystemAnalyzer,
    ITrendEvaluator,
)
from .models import ImprovementReport, SystemMetric


class SelfImprovementManager(RuntimeComponent):
    """Orchestrates the Self-Improvement optimization loop."""

    def __init__(
        self,
        aggregator: IMetricsAggregator,
        analyzer: ISystemAnalyzer,
        optimizer: IBehaviorOptimizer,
        recommender: IImprovementRecommender,
        evaluator: ITrendEvaluator,
        policy_engine: IPolicyEngine,
        persistence: IImprovementPersistence,
        event_bus: EventBus,
        logger: AsyncLogger
    ) -> None:
        self._aggregator = aggregator
        self._analyzer = analyzer
        self._optimizer = optimizer
        self._recommender = recommender
        self._evaluator = evaluator
        self._policy_engine = policy_engine
        self._persistence = persistence
        self._event_bus = event_bus
        self._logger = logger

        self._lock = threading.RLock()
        
        self._state = ComponentState.INITIALIZED
        self._metadata = ComponentMetadata(
            id="core.improvement",
            name="Self-Improvement Engine",
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
        self._logger.info("Starting Self-Improvement Engine...")
        self._state = ComponentState.RUNNING
        self._logger.info("Self-Improvement Engine started.")

    async def stop(self) -> None:
        if self._state != ComponentState.RUNNING:
            return

        self._state = ComponentState.STOPPING
        self._logger.info("Stopping Self-Improvement Engine...")
        self._state = ComponentState.STOPPED
        self._logger.info("Self-Improvement Engine stopped.")

    async def health(self) -> HealthReport:
        try:
            return HealthReport(
                component_id=self.metadata.id,
                state=HealthState.HEALTHY,
                details={}
            )
        except Exception as e:  # noqa: BLE001
            return HealthReport(
                component_id=self.metadata.id,
                state=HealthState.UNHEALTHY,
                error=str(e)
            )

    def track_metric(self, metric: SystemMetric) -> None:
        self._aggregator.add_metric(metric)

    def analyze(self) -> None:
        """Executes the analysis and optimization generation pipeline."""
        with self._lock:
            try:
                # 1. Aggregate
                snapshot = self._aggregator.get_snapshot()
                if not snapshot.metrics:
                    return # Nothing to analyze
                
                self._persistence.save_snapshot(snapshot)
                
                # 2. Analyze
                analysis_results = self._analyzer.analyze(snapshot)
                self._publish_event("improvement.analysis.completed", {"snapshot_id": snapshot.id.value})
                
                # 3. Optimize (generate recommendations)
                raw_recs = self._optimizer.optimize(analysis_results)
                
                # 4. Enforce Policies
                safe_recs = []
                historical_recs = self._persistence.get_recommendations(limit=100)
                
                for rec in raw_recs:
                    action = self._policy_engine.evaluate_recommendation(rec, historical_recs)
                    if action == PolicyAction.ALLOW:
                        safe_recs.append(rec)
                        self._persistence.save_recommendation(rec)
                        self._publish_event("improvement.recommendation.created", {"rec_id": rec.id.value})
                    else:
                        self._publish_event("improvement.policy.blocked", {"rec_id": rec.id.value, "reason": action.value})

                # 5. Evaluate trends against history
                historical_snaps = self._persistence.get_snapshots(limit=10)
                trends = self._evaluator.evaluate(snapshot, historical_snaps)

                # 6. Report
                report = self._recommender.generate_report(snapshot, trends, safe_recs)
                self._persistence.save_report(report)
                self._publish_event("improvement.report.generated", {"report_id": report.id.value})

            except Exception as e:
                raise AnalysisError(f"Failed to analyze metrics: {e}") from e

    def history(self) -> builtins.list[ImprovementReport]:
        return self._persistence.get_reports(limit=50)
        
    def _publish_event(self, topic: str, payload: dict[str, str]) -> None:
        event = Event(
            topic=topic,
            payload=payload,
            source=self.metadata.id
        )
        self._event_bus.publish(event)

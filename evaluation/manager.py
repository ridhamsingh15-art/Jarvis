from core.events.bus import EventBus
from core.models import Event
from core.models.primitives import Identifier
from core.runtime.enums import ComponentState, HealthState
from core.runtime.interfaces import RuntimeComponent
from core.runtime.models import ComponentMetadata, HealthReport

from .benchmark import BenchmarkSuite
from .datasets import DatasetRegistry, build_default_datasets
from .judge import EvaluationJudge
from .leaderboard import Leaderboard
from .metrics import EvaluationMetrics
from .regression import RegressionRunner
from .replay import MissionReplay
from .report import ReportGenerator


class EvaluationManager(RuntimeComponent):
    """RuntimeComponent that ties the entire JET evaluation pipeline together:
    dataset loading, scenario execution, judging, metric aggregation,
    regression checking, leaderboard updates, and report generation."""

    def __init__(self, event_bus: EventBus) -> None:
        self._id = Identifier("manager.evaluation")
        self.event_bus = event_bus

        self.registry = DatasetRegistry()
        self.judge = EvaluationJudge()
        self.metrics = EvaluationMetrics()
        self.leaderboard = Leaderboard()
        self.replay = MissionReplay()
        self.reporter = ReportGenerator()

        self.suite = BenchmarkSuite(self.registry)
        self.regression = RegressionRunner(self.suite, self.judge)

        self._is_running = False

    @property
    def id(self) -> Identifier:
        return self._id

    @property
    def metadata(self) -> ComponentMetadata:
        return ComponentMetadata(
            id=self._id.value,
            name="Evaluation & Training Platform",
            version="1.0.0",
        )

    @property
    def state(self) -> ComponentState:
        return ComponentState.RUNNING if self._is_running else ComponentState.STOPPED

    async def initialize(self) -> None:
        for ds in build_default_datasets():
            self.registry.register(ds)

    async def start(self) -> None:
        self._is_running = True

    async def stop(self) -> None:
        self._is_running = False

    async def health(self) -> HealthReport:
        return HealthReport(
            component_id=self._id.value,
            state=HealthState.HEALTHY if self._is_running else HealthState.UNKNOWN,
        )

    async def run_full_evaluation(self) -> dict[str, str]:
        """Execute the complete evaluation pipeline and return reports."""
        await self.event_bus.publish_async(
            Event(topic="evaluation.started", payload={})
        )

        # Run benchmarks
        all_results = self.suite.run_all()

        # Judge and aggregate
        for category, results in all_results.items():
            verdicts = self.judge.judge_batch(results)
            cm = self.metrics.aggregate(category, results, verdicts)
            self.leaderboard.submit(
                name=f"default_{category}",
                category=category,
                score=cm.avg_quality,
            )

        # Regression
        regressions = self.regression.run_regression()

        # Reports
        json_report = self.reporter.generate_json(
            self.metrics, regressions, self.leaderboard
        )
        md_report = self.reporter.generate_markdown(
            self.metrics, regressions, self.leaderboard
        )
        html_report = self.reporter.generate_html(
            self.metrics, regressions, self.leaderboard
        )

        await self.event_bus.publish_async(
            Event(
                topic="evaluation.completed",
                payload={"success_rate": self.metrics.overall_success_rate()},
            )
        )

        return {
            "json": json_report,
            "markdown": md_report,
            "html": html_report,
        }

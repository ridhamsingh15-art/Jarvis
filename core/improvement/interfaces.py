import builtins
from abc import ABC, abstractmethod
from typing import Any

from .enums import PolicyAction
from .models import (
    ImprovementReport,
    MetricSnapshot,
    OptimizationRecommendation,
    PerformanceTrend,
    SystemMetric,
)


class IMetricsAggregator(ABC):
    @abstractmethod
    def add_metric(self, metric: SystemMetric) -> None:
        pass

    @abstractmethod
    def get_snapshot(self) -> MetricSnapshot:
        pass


class ISystemAnalyzer(ABC):
    @abstractmethod
    def analyze(self, snapshot: MetricSnapshot) -> dict[str, Any]:
        pass


class IBehaviorOptimizer(ABC):
    @abstractmethod
    def optimize(self, analysis_results: dict[str, Any]) -> builtins.list[OptimizationRecommendation]:
        pass


class ITrendEvaluator(ABC):
    @abstractmethod
    def evaluate(self, current: MetricSnapshot, historical: builtins.list[MetricSnapshot]) -> builtins.list[PerformanceTrend]:
        pass


class IPolicyEngine(ABC):
    @abstractmethod
    def evaluate_recommendation(
        self, 
        recommendation: OptimizationRecommendation, 
        history: builtins.list[OptimizationRecommendation]
    ) -> PolicyAction:
        pass


class IImprovementRecommender(ABC):
    @abstractmethod
    def generate_report(
        self, 
        snapshot: MetricSnapshot, 
        trends: builtins.list[PerformanceTrend], 
        recommendations: builtins.list[OptimizationRecommendation]
    ) -> ImprovementReport:
        pass


class IImprovementPersistence(ABC):
    @abstractmethod
    def save_snapshot(self, snapshot: MetricSnapshot) -> None:
        pass

    @abstractmethod
    def get_snapshots(self, limit: int = 10) -> builtins.list[MetricSnapshot]:
        pass

    @abstractmethod
    def save_report(self, report: ImprovementReport) -> None:
        pass

    @abstractmethod
    def get_reports(self, limit: int = 10) -> builtins.list[ImprovementReport]:
        pass

    @abstractmethod
    def save_recommendation(self, recommendation: OptimizationRecommendation) -> None:
        pass

    @abstractmethod
    def get_recommendations(self, limit: int = 50) -> builtins.list[OptimizationRecommendation]:
        pass

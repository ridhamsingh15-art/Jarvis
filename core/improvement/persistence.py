import builtins
import copy
import threading

from .interfaces import IImprovementPersistence
from .models import ImprovementReport, MetricSnapshot, OptimizationRecommendation


class InMemoryImprovementPersistence(IImprovementPersistence):
    """Thread-safe database proxy storing historical reports natively."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._snapshots: builtins.list[MetricSnapshot] = []
        self._reports: builtins.list[ImprovementReport] = []
        self._recommendations: builtins.list[OptimizationRecommendation] = []

    def save_snapshot(self, snapshot: MetricSnapshot) -> None:
        with self._lock:
            self._snapshots.append(copy.deepcopy(snapshot))

    def get_snapshots(self, limit: int = 10) -> builtins.list[MetricSnapshot]:
        with self._lock:
            return [copy.deepcopy(s) for s in self._snapshots[-limit:]]

    def save_report(self, report: ImprovementReport) -> None:
        with self._lock:
            self._reports.append(copy.deepcopy(report))

    def get_reports(self, limit: int = 10) -> builtins.list[ImprovementReport]:
        with self._lock:
            return [copy.deepcopy(r) for r in self._reports[-limit:]]

    def save_recommendation(self, recommendation: OptimizationRecommendation) -> None:
        with self._lock:
            self._recommendations.append(copy.deepcopy(recommendation))

    def get_recommendations(self, limit: int = 50) -> builtins.list[OptimizationRecommendation]:
        with self._lock:
            return [copy.deepcopy(r) for r in self._recommendations[-limit:]]

import builtins
import threading
import uuid

from core.models.primitives import Identifier

from .interfaces import IMetricsAggregator
from .models import MetricSnapshot, SystemMetric


class DefaultMetricsAggregator(IMetricsAggregator):
    """Aggregates active metrics thread-safely."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._metrics: builtins.list[SystemMetric] = []

    def add_metric(self, metric: SystemMetric) -> None:
        with self._lock:
            self._metrics.append(metric)

    def get_snapshot(self) -> MetricSnapshot:
        with self._lock:
            snapshot = MetricSnapshot(
                id=Identifier(f"snap_{uuid.uuid4().hex[:8]}"),
                metrics=list(self._metrics)
            )
            self._metrics.clear()
            return snapshot

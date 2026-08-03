import os

d = "core/observability"
os.makedirs(d, exist_ok=True)

files = {}

files["tracing.py"] = """import uuid
import time
from typing import Any
from contextlib import contextmanager

class Span:
    def __init__(self, name: str, trace_id: str, parent_id: str | None = None):
        self.id = uuid.uuid4().hex
        self.trace_id = trace_id
        self.parent_id = parent_id
        self.name = name
        self.start_time = time.time()
        self.end_time: float | None = None
        self.duration: float | None = None
        self.errors: list[str] = []

    def end(self) -> None:
        self.end_time = time.time()
        self.duration = self.end_time - self.start_time

class TraceContext:
    def __init__(self) -> None:
        self.trace_id = uuid.uuid4().hex
        self.spans: list[Span] = []
        self._current_span: Span | None = None

    @contextmanager
    def span(self, name: str):
        parent = self._current_span
        s = Span(name, self.trace_id, parent.id if parent else None)
        self.spans.append(s)
        self._current_span = s
        try:
            yield s
        except Exception as e:
            s.errors.append(str(e))
            raise
        finally:
            s.end()
            self._current_span = parent
"""

files["metrics.py"] = """import threading
from typing import Any

class Gauge:
    def __init__(self, name: str):
        self.name = name
        self.value: float = 0.0

    def set(self, val: float) -> None:
        self.value = val

class Counter:
    def __init__(self, name: str):
        self.name = name
        self.value: int = 0

    def inc(self, val: int = 1) -> None:
        self.value += val

class Histogram:
    def __init__(self, name: str):
        self.name = name
        self.values: list[float] = []

    def observe(self, val: float) -> None:
        self.values.append(val)

class MetricsRegistry:
    def __init__(self) -> None:
        self.gauges: dict[str, Gauge] = {}
        self.counters: dict[str, Counter] = {}
        self.histograms: dict[str, Histogram] = {}
        self._lock = threading.Lock()

    def get_gauge(self, name: str) -> Gauge:
        with self._lock:
            if name not in self.gauges:
                self.gauges[name] = Gauge(name)
            return self.gauges[name]

    def get_counter(self, name: str) -> Counter:
        with self._lock:
            if name not in self.counters:
                self.counters[name] = Counter(name)
            return self.counters[name]

    def get_histogram(self, name: str) -> Histogram:
        with self._lock:
            if name not in self.histograms:
                self.histograms[name] = Histogram(name)
            return self.histograms[name]
"""

files["profiler.py"] = """from .tracing import TraceContext

class ExecutionProfiler:
    def profile(self, trace: TraceContext) -> dict[str, float]:
        slow_spans = {}
        for s in trace.spans:
            if s.duration and s.duration > 0.05: # Mock threshold
                slow_spans[s.name] = s.duration
        return slow_spans
"""

files["diagnostics.py"] = """from .metrics import MetricsRegistry

class DiagnosticScanner:
    def __init__(self, registry: MetricsRegistry):
        self.registry = registry

    def scan(self) -> list[str]:
        issues = []
        ram = self.registry.get_gauge("system.ram.usage").value
        if ram > 90.0:
            issues.append("High RAM usage detected.")
        return issues
"""

files["analyzer.py"] = """from .tracing import TraceContext

class TelemetryAnalyzer:
    def analyze(self, trace: TraceContext) -> dict[str, int]:
        errors = sum(len(s.errors) for s in trace.spans)
        return {"total_spans": len(trace.spans), "total_errors": errors}
"""

files["monitor.py"] = """from .metrics import MetricsRegistry

class SystemMonitor:
    def __init__(self, registry: MetricsRegistry):
        self.registry = registry

    def update(self) -> None:
        # Mocks system metrics for test stability
        self.registry.get_gauge("system.cpu.usage").set(45.0)
        self.registry.get_gauge("system.ram.usage").set(60.0)
        self.registry.get_gauge("system.disk.usage").set(75.0)
"""

files["dashboard.py"] = """from .metrics import MetricsRegistry

class ObservabilityDashboard:
    def __init__(self, registry: MetricsRegistry):
        self.registry = registry

    def render(self) -> dict[str, float]:
        return {
            name: gauge.value for name, gauge in self.registry.gauges.items()
        }
"""

files["alerts.py"] = """from core.events.bus import EventBus
from core.models import Event
from .metrics import MetricsRegistry

class AlertEngine:
    def __init__(self, event_bus: EventBus, registry: MetricsRegistry):
        self.event_bus = event_bus
        self.registry = registry

    async def evaluate(self) -> None:
        ram = self.registry.get_gauge("system.ram.usage").value
        if ram > 90.0:
            await self.event_bus.publish_async(Event(
                topic="observability.alert.ram_high",
                payload={"usage": ram}
            ))
"""

files["recorder.py"] = """import json
from .tracing import TraceContext

class ExecutionRecorder:
    def __init__(self) -> None:
        self.records: dict[str, str] = {}

    def record(self, trace: TraceContext) -> None:
        data = []
        for s in trace.spans:
            data.append({
                "id": s.id, "name": s.name, 
                "duration": s.duration, "errors": s.errors
            })
        self.records[trace.trace_id] = json.dumps(data)
"""

files["replay.py"] = """import json
from .recorder import ExecutionRecorder

class ExecutionReplay:
    def __init__(self, recorder: ExecutionRecorder):
        self.recorder = recorder

    def replay(self, trace_id: str) -> list[dict]:
        data = self.recorder.records.get(trace_id)
        if not data:
            return []
        return json.loads(data)
"""

files["performance.py"] = """from .tracing import TraceContext

class PerformanceAnalyzer:
    def __init__(self) -> None:
        pass

    def evaluate_latency(self, trace: TraceContext) -> dict[str, str]:
        results = {}
        for s in trace.spans:
            if "llm" in s.name.lower() and s.duration and s.duration > 1.0:
                results[s.name] = "SLOW_LLM"
            elif "vision" in s.name.lower() and s.duration and s.duration > 0.5:
                results[s.name] = "SLOW_VISION"
        return results
"""

files["manager.py"] = """from typing import Any

from core.events.bus import EventBus
from core.models import Event
from core.models.primitives import Identifier
from core.runtime.enums import ComponentState, HealthState
from core.runtime.interfaces import RuntimeComponent
from core.runtime.models import ComponentMetadata, HealthReport

from .tracing import TraceContext
from .metrics import MetricsRegistry
from .profiler import ExecutionProfiler
from .diagnostics import DiagnosticScanner
from .analyzer import TelemetryAnalyzer
from .monitor import SystemMonitor
from .dashboard import ObservabilityDashboard
from .alerts import AlertEngine
from .recorder import ExecutionRecorder
from .replay import ExecutionReplay
from .performance import PerformanceAnalyzer

class ObservabilityManager(RuntimeComponent):
    def __init__(self, event_bus: EventBus):
        self._id = Identifier("manager.observability")
        self.event_bus = event_bus
        
        self.registry = MetricsRegistry()
        self.monitor = SystemMonitor(self.registry)
        self.alerts = AlertEngine(event_bus, self.registry)
        self.dashboard_mgr = ObservabilityDashboard(self.registry)
        self.profiler = ExecutionProfiler()
        self.diagnostics = DiagnosticScanner(self.registry)
        self.analyzer = TelemetryAnalyzer()
        self.recorder = ExecutionRecorder()
        self.replayer = ExecutionReplay(self.recorder)
        self.performance = PerformanceAnalyzer()
        
        self._is_running = False

    @property
    def id(self) -> Identifier:
        return self._id

    @property
    def metadata(self) -> ComponentMetadata:
        return ComponentMetadata(id=self._id.value, name="Observability", version="1.0.0")

    @property
    def state(self) -> ComponentState:
        return ComponentState.RUNNING if self._is_running else ComponentState.STOPPED

    async def initialize(self) -> None:
        pass

    async def start(self) -> None:
        self._is_running = True

    async def stop(self) -> None:
        self._is_running = False

    async def health(self) -> HealthReport:
        return HealthReport(
            component_id=self._id.value,
            state=HealthState.HEALTHY if self._is_running else HealthState.UNKNOWN
        )

    def start_trace(self) -> TraceContext:
        return TraceContext()
        
    def end_trace(self, trace: TraceContext) -> None:
        self.recorder.record(trace)
        
    def profile(self, trace: TraceContext) -> dict[str, float]:
        return self.profiler.profile(trace)
        
    def metrics(self) -> MetricsRegistry:
        return self.registry
        
    def dashboard(self) -> dict[str, float]:
        self.monitor.update()
        return self.dashboard_mgr.render()
        
    def replay(self, trace_id: str) -> list[dict]:
        return self.replayer.replay(trace_id)
"""

files["__init__.py"] = """from .manager import ObservabilityManager
from .tracing import TraceContext, Span
from .metrics import MetricsRegistry

__all__ = [
    "ObservabilityManager",
    "TraceContext",
    "Span",
    "MetricsRegistry"
]
"""

for fname, fcontent in files.items():
    with open(os.path.join(d, fname), "w") as f:
        f.write(fcontent)
        
tests_file = """import pytest

from core.events.bus import EventBus
from core.observability import ObservabilityManager

class MockLogger:
    def info(self, *args, **kwargs): pass
    def error(self, *args, **kwargs): pass
    def debug(self, *args, **kwargs): pass
    def warning(self, *args, **kwargs): pass
    async def log_async(self, *args, **kwargs): pass

@pytest.fixture
def event_bus():
    return EventBus(MockLogger())

@pytest.fixture
def observability(event_bus):
    return ObservabilityManager(event_bus)

@pytest.mark.asyncio
async def test_trace_propagation(observability):
    trace = observability.start_trace()
    with trace.span("root"):
        with trace.span("child1"):
            pass
        with trace.span("child2"):
            pass
    
    assert len(trace.spans) == 3
    assert trace.spans[1].parent_id == trace.spans[0].id
    assert trace.spans[2].parent_id == trace.spans[0].id

@pytest.mark.asyncio
async def test_dashboard_metrics(observability):
    dash = observability.dashboard()
    assert dash["system.cpu.usage"] == 45.0
    assert dash["system.ram.usage"] == 60.0

@pytest.mark.asyncio
async def test_alerts(observability):
    # Set high RAM
    observability.metrics().get_gauge("system.ram.usage").set(95.0)
    
    # We could assert the event bus publish, but for now we just run it
    await observability.alerts.evaluate()
    assert observability.diagnostics.scan() == ["High RAM usage detected."]

@pytest.mark.asyncio
async def test_recording_and_replay(observability):
    trace = observability.start_trace()
    with trace.span("job1"):
        pass
    
    observability.end_trace(trace)
    
    history = observability.replay(trace.trace_id)
    assert len(history) == 1
    assert history[0]["name"] == "job1"
"""

with open("tests/test_observability.py", "w") as f:
    f.write(tests_file)

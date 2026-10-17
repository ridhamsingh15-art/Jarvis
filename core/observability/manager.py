
from core.events.bus import EventBus
from core.models.primitives import Identifier
from core.runtime.enums import ComponentState, HealthState
from core.runtime.interfaces import RuntimeComponent
from core.runtime.models import ComponentMetadata, HealthReport

from .alerts import AlertEngine
from .analyzer import TelemetryAnalyzer
from .dashboard import ObservabilityDashboard
from .diagnostics import DiagnosticScanner
from .metrics import MetricsRegistry
from .monitor import SystemMonitor
from .performance import PerformanceAnalyzer
from .profiler import ExecutionProfiler
from .recorder import ExecutionRecorder
from .replay import ExecutionReplay
from .tracing import TraceContext


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

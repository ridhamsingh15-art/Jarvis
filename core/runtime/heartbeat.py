import threading

from core.events import EventBus
from core.models import Event

from .health import HealthMonitor
from .models import HeartbeatPayload


class HeartbeatService:
    """Daemon thread emitting system heartbeats at configured intervals."""
    
    def __init__(self, event_bus: EventBus, health_monitor: HealthMonitor, interval_seconds: float = 5.0):
        self._event_bus = event_bus
        self._health_monitor = health_monitor
        self._interval = interval_seconds
        
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._kernel = None  # Reference injected later to get kernel state

    def set_kernel(self, kernel) -> None:
        self._kernel = kernel

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
            
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, name="Jarvis-Heartbeat-Thread", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)
            
    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            if self._kernel:
                state = self._kernel.state()
                uptime = self._kernel.uptime()
                
                # Check health
                reports = self._health_monitor.get_reports()
                from .enums import HealthState
                overall = HealthState.HEALTHY
                for r in reports:
                    if r.state == HealthState.UNHEALTHY:
                        overall = HealthState.UNHEALTHY
                        break
                    elif r.state == HealthState.DEGRADED:
                        overall = HealthState.DEGRADED
                
                payload = HeartbeatPayload(
                    component_id="runtime.kernel",
                    status=overall,
                    state=state.value,
                    active_components=len(self._health_monitor._registry.get_all()),
                    uptime_seconds=uptime
                )
                
                event = Event(topic="runtime.heartbeat", payload=payload.to_dict(), source="runtime.heartbeat")
                self._event_bus.publish(event)
                
            self._stop_event.wait(self._interval)

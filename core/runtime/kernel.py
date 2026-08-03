import asyncio
import threading
import time
from dataclasses import asdict

from core.bootstrap import Runtime
from core.models import Event

from .enums import RuntimeState
from .exceptions import RuntimeError
from .health import HealthMonitor
from .heartbeat import HeartbeatService
from .models import HealthReport, StateChangePayload
from .registry import ComponentRegistry


class RuntimeKernel:
    """The central runtime coordinator for JARVIS AIOS."""
    
    def __init__(self, runtime: Runtime):
        self._foundation_runtime = runtime
        self._logger = runtime.logger
        self._event_bus = runtime.event_bus
        
        self._registry = ComponentRegistry()
        self._health_monitor = HealthMonitor(self._registry)
        
        # Configure heartbeat interval based on config (or default to 5s)
        try:
            config_snap = runtime.container.resolve("ConfigSnapshot")  # type: ignore
            interval = getattr(config_snap, "heartbeat_interval", 5.0)
        except Exception:  # noqa: BLE001
            interval = 5.0
            
        self._heartbeat = HeartbeatService(self._event_bus, self._health_monitor, interval)
        self._heartbeat.set_kernel(self)
        
        self._state = RuntimeState.STOPPED
        self._state_lock = threading.Lock()
        self._start_time: float | None = None
        
        self._loop = asyncio.new_event_loop()
        self._loop_thread = threading.Thread(target=self._loop.run_forever, daemon=True, name="Jarvis-Runtime-Loop")

    def state(self) -> RuntimeState:
        with self._state_lock:
            return self._state

    def uptime(self) -> float:
        if not self._start_time:
            return 0.0
        return time.time() - self._start_time
        
    def health_report(self):
        reports = self._health_monitor.get_reports()
        from .enums import HealthState
        overall = HealthState.HEALTHY
        for r in reports:
            if r.state == HealthState.UNHEALTHY:
                overall = HealthState.UNHEALTHY
                break
            elif r.state == HealthState.DEGRADED:
                overall = HealthState.DEGRADED
        return HealthReport(
            component_id="runtime.kernel",
            state=overall,
            details={"components": {r.component_id: asdict(r) for r in reports}}
        )
        
    def register_component(self, component) -> None:
        self._registry.register(component)
        self._publish_event("runtime.component.registered", {"name": component.metadata.name})

    def _transition_state(self, new_state: RuntimeState, reason: str = "") -> None:
        with self._state_lock:
            old_state = self._state
            self._state = new_state
            
        payload = StateChangePayload(
            component_id="runtime.kernel",
            old_state=old_state.value, 
            new_state=new_state.value, 
            reason=reason
        )
        self._publish_event(f"runtime.{new_state.value.lower()}", asdict(payload))

    def _publish_event(self, topic: str, payload: dict) -> None:
        self._event_bus.publish(Event(topic=topic, payload=payload, source="runtime.kernel"))

    def start(self) -> None:
        with self._state_lock:
            if self._state not in (RuntimeState.STOPPED, RuntimeState.FAILED):
                raise RuntimeError(f"Cannot start kernel from state {self._state}")
                
        self._logger.info("Runtime Kernel is starting...")
        self._transition_state(RuntimeState.STARTING)
        self._start_time = time.time()
        
        # Start the runtime loop thread
        self._loop_thread.start()
        
        # Start all registered components in order
        try:
            for component in self._registry.get_all():
                asyncio.run_coroutine_threadsafe(component.start(), self._loop).result()
                self._publish_event("runtime.component.started", {"name": component.metadata.name})
                
            # Start background monitors
            asyncio.run_coroutine_threadsafe(self._health_monitor.start(), self._loop).result()
            self._heartbeat.start()
            self._transition_state(RuntimeState.RUNNING)
            self._logger.info("Runtime Kernel started successfully.")
            
        except Exception as e:  # noqa: BLE001
            self._logger.error("Failed to start Runtime Kernel", error=str(e))
            self._transition_state(RuntimeState.FAILED, reason=str(e))
            self.stop() # Attempt graceful rollback

    def stop(self) -> None:
        with self._state_lock:
            if self._state == RuntimeState.STOPPED:
                return
                
        self._logger.info("Runtime Kernel is stopping...")
        self._transition_state(RuntimeState.STOPPING)
        
        self._heartbeat.stop()
        asyncio.run_coroutine_threadsafe(self._health_monitor.stop(), self._loop).result()
        
        # Stop components in reverse registry order
        components = self._registry.get_all()
        for comp in reversed(components):
            try:
                asyncio.run_coroutine_threadsafe(comp.stop(), self._loop).result()
                self._publish_event("runtime.component.stopped", {"name": comp.metadata.name})
            except Exception as e:  # noqa: BLE001
                self._logger.error(f"Error stopping component {comp.metadata.name}", error=str(e))
                
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._loop_thread.join(timeout=2.0)
                
        # Foundation Shutdown
        self._foundation_runtime.shutdown()
        
        self._transition_state(RuntimeState.STOPPED)
        self._start_time = None
        self._logger.info("Runtime Kernel stopped.")

    def pause(self) -> None:
        with self._state_lock:
            if self._state != RuntimeState.RUNNING:
                raise RuntimeError(f"Cannot pause kernel from state {self._state}")
        self._transition_state(RuntimeState.PAUSED)
        self._logger.info("Runtime Kernel paused.")

    def resume(self) -> None:
        with self._state_lock:
            if self._state != RuntimeState.PAUSED:
                raise RuntimeError(f"Cannot resume kernel from state {self._state}")
        self._transition_state(RuntimeState.RUNNING)
        self._logger.info("Runtime Kernel resumed.")

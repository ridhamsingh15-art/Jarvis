import time
import threading
from typing import Optional

from core.bootstrap import Runtime
from core.models import Event
from core.errors import InternalError

from .enums import RuntimeState
from .exceptions import RuntimeError
from .registry import RuntimeRegistry
from .health import HealthMonitor
from .heartbeat import HeartbeatService
from .models import StateChangePayload

class RuntimeKernel:
    """The central runtime coordinator for JARVIS AIOS."""
    
    def __init__(self, runtime: Runtime):
        self._foundation_runtime = runtime
        self._logger = runtime.logger
        self._event_bus = runtime.event_bus
        
        self._registry = RuntimeRegistry()
        self._health_monitor = HealthMonitor(self._registry)
        
        # Configure heartbeat interval based on config (or default to 5s)
        try:
            config_snap = runtime.container.resolve("ConfigSnapshot")
            interval = getattr(config_snap, "heartbeat_interval", 5.0)
        except Exception:
            interval = 5.0
            
        self._heartbeat = HeartbeatService(self._event_bus, self._health_monitor, interval)
        self._heartbeat.set_kernel(self)
        
        self._state = RuntimeState.STOPPED
        self._state_lock = threading.Lock()
        self._start_time: Optional[float] = None

    def state(self) -> RuntimeState:
        with self._state_lock:
            return self._state

    def uptime(self) -> float:
        if not self._start_time:
            return 0.0
        return time.time() - self._start_time
        
    def health_report(self):
        return self._health_monitor.check_health()
        
    def register_component(self, component) -> None:
        self._registry.register(component)
        self._publish_event("runtime.component.registered", {"name": component.metadata().name})

    def _transition_state(self, new_state: RuntimeState, reason: str = "") -> None:
        with self._state_lock:
            old_state = self._state
            self._state = new_state
            
        payload = StateChangePayload(old_state=old_state, new_state=new_state, reason=reason)
        self._publish_event(f"runtime.{new_state.value.lower()}", payload.to_dict())

    def _publish_event(self, topic: str, payload: dict) -> None:
        self._event_bus.publish(Event(topic=topic, payload=payload, source="runtime.kernel"))

    def start(self) -> None:
        with self._state_lock:
            if self._state not in (RuntimeState.STOPPED, RuntimeState.FAILED):
                raise RuntimeError(f"Cannot start kernel from state {self._state}")
                
        self._logger.info("Runtime Kernel is starting...")
        self._transition_state(RuntimeState.STARTING)
        self._start_time = time.time()
        
        try:
            # Start all components in registry order
            for comp in self._registry.list_components():
                comp.start()
                self._publish_event("runtime.component.started", {"name": comp.metadata().name})
                
            self._heartbeat.start()
            self._transition_state(RuntimeState.RUNNING)
            self._logger.info("Runtime Kernel started successfully.")
            
        except Exception as e:
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
        
        # Stop components in reverse registry order
        components = self._registry.list_components()
        for comp in reversed(components):
            try:
                comp.stop()
                self._publish_event("runtime.component.stopped", {"name": comp.metadata().name})
            except Exception as e:
                self._logger.error(f"Error stopping component {comp.metadata().name}", error=str(e))
                
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

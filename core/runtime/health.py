"""
Background health monitoring for the runtime.
"""
import asyncio
from collections.abc import Awaitable, Callable

from .enums import HealthState
from .models import HealthReport
from .registry import ComponentRegistry


class HealthMonitor:
    """Periodically polls components for health status."""

    def __init__(self, registry: ComponentRegistry, interval_seconds: float = 10.0) -> None:
        self._registry = registry
        self._interval = interval_seconds
        self._task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()
        self._last_reports: dict[str, HealthReport] = {}
        # Optional callback for emitting events (e.g. to EventBus)
        self.on_health_degraded: Callable[[HealthReport], Awaitable[None]] | None = None

    async def start(self) -> None:
        if self._task is not None:
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._monitor_loop())

    async def stop(self) -> None:
        if self._task is None:
            return
        self._stop_event.set()
        await self._task
        self._task = None

    async def _monitor_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                await self._poll_health()
            except Exception:  # noqa: BLE001, S110
                pass  # Suppress global polling crashes
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=self._interval)
            except asyncio.TimeoutError:
                pass

    async def _poll_health(self) -> None:
        components = self._registry.get_all()
        for comp in components:
            try:
                report = await comp.health()
            except Exception as e:  # noqa: BLE001
                report = HealthReport(
                    component_id=comp.metadata.id,
                    state=HealthState.UNHEALTHY,
                    error=f"Health check crashed: {e}"
                )

            # Check if state degraded
            prev_report = self._last_reports.get(comp.metadata.id)
            if (prev_report is None or prev_report.state == HealthState.HEALTHY) and report.state != HealthState.HEALTHY and self.on_health_degraded:
                await self.on_health_degraded(report)

            self._last_reports[comp.metadata.id] = report

    def get_reports(self) -> list[HealthReport]:
        return list(self._last_reports.values())

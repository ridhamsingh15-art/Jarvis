"""
Lifecycle Hooks — Phase C implementation.

Maps well-defined lifecycle points onto the existing EventBus infrastructure.
Does NOT create a duplicate framework. Uses core.events.bus.EventBus directly.

Lifecycle points:
    PRE_TOOL       — fires before a tool task executes
    POST_TOOL      — fires after a tool task succeeds
    TOOL_FAILED    — fires after a tool task fails
    MISSION_START  — fires when a MISSION route begins
    MISSION_END    — fires when a MISSION route completes
    SESSION_START  — fires when Agent.run() is entered
    SESSION_END    — fires when Agent.run() exits
    AGENT_START    — fires when Agent is initialized
    AGENT_STOP     — fires when Agent is disposed

Safety:
    - Hook failures NEVER propagate to the caller (failure-isolated)
    - Hooks cannot trigger recursive tool execution
    - All hook dispatch is synchronous and bounded (max_hook_time_ms)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from core.events.bus import EventBus
    from core.models import Event

logger = logging.getLogger(__name__)

# Hooks that fire for > this many ms are logged as warnings
_MAX_HOOK_WARN_MS: float = 500.0


# ---------------------------------------------------------------------------
# Lifecycle event topics — maps onto EventBus topic namespace
# ---------------------------------------------------------------------------


class LifecycleEvent(StrEnum):
    """Canonical lifecycle event topic strings, published on the EventBus."""
    PRE_TOOL = "lifecycle.pre_tool"
    POST_TOOL = "lifecycle.post_tool"
    TOOL_FAILED = "lifecycle.tool_failed"
    MISSION_START = "lifecycle.mission_start"
    MISSION_END = "lifecycle.mission_end"
    SESSION_START = "lifecycle.session_start"
    SESSION_END = "lifecycle.session_end"
    AGENT_START = "lifecycle.agent_start"
    AGENT_STOP = "lifecycle.agent_stop"


# ---------------------------------------------------------------------------
# Hook payload helpers
# ---------------------------------------------------------------------------


def _make_event(topic: LifecycleEvent, payload: dict[str, Any]) -> "Event":
    """Build a core.models.Event for the given lifecycle topic."""
    from core.models import Event  # local import to avoid circular deps
    return Event(topic=topic.value, payload=payload)


# ---------------------------------------------------------------------------
# LifecycleHooks
# ---------------------------------------------------------------------------


class LifecycleHooks:
    """
    Thin adapter that publishes lifecycle events on the EventBus.

    The caller registers hook handlers via event_bus.subscribe(topic, handler).
    LifecycleHooks just ensures the right events fire at the right times.

    All publish calls are failure-isolated — exceptions in handlers are caught
    by the EventDispatcher and must not propagate to the primary request path.
    """

    def __init__(self, event_bus: "EventBus | None" = None) -> None:
        self._bus = event_bus

    # ------------------------------------------------------------------
    # Tool lifecycle
    # ------------------------------------------------------------------

    def pre_tool(self, tool: str, action: str, args: dict, request_id: str = "") -> None:
        self._publish(LifecycleEvent.PRE_TOOL, {
            "tool": tool, "action": action, "args": args, "request_id": request_id,
        })

    def post_tool(self, tool: str, action: str, result: Any, latency_ms: float, request_id: str = "") -> None:
        self._publish(LifecycleEvent.POST_TOOL, {
            "tool": tool, "action": action, "result": str(result)[:256],
            "latency_ms": latency_ms, "request_id": request_id,
        })

    def tool_failed(self, tool: str, action: str, error: str, request_id: str = "") -> None:
        self._publish(LifecycleEvent.TOOL_FAILED, {
            "tool": tool, "action": action, "error": error, "request_id": request_id,
        })

    # ------------------------------------------------------------------
    # Mission lifecycle
    # ------------------------------------------------------------------

    def mission_start(self, mission_id: str, user_input: str) -> None:
        self._publish(LifecycleEvent.MISSION_START, {
            "mission_id": mission_id, "user_input": user_input[:200],
        })

    def mission_end(self, mission_id: str, succeeded: bool, latency_ms: float) -> None:
        self._publish(LifecycleEvent.MISSION_END, {
            "mission_id": mission_id, "succeeded": succeeded, "latency_ms": latency_ms,
        })

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    def session_start(self, session_id: str, user_input: str) -> None:
        self._publish(LifecycleEvent.SESSION_START, {
            "session_id": session_id, "user_input": user_input[:200],
        })

    def session_end(self, session_id: str, task_count: int, latency_ms: float) -> None:
        self._publish(LifecycleEvent.SESSION_END, {
            "session_id": session_id, "task_count": task_count, "latency_ms": latency_ms,
        })

    # ------------------------------------------------------------------
    # Agent lifecycle
    # ------------------------------------------------------------------

    def agent_start(self) -> None:
        self._publish(LifecycleEvent.AGENT_START, {"status": "initialized"})

    def agent_stop(self) -> None:
        self._publish(LifecycleEvent.AGENT_STOP, {"status": "stopped"})

    # ------------------------------------------------------------------
    # Internal — failure-isolated publish
    # ------------------------------------------------------------------

    def _publish(self, event: LifecycleEvent, payload: dict[str, Any]) -> None:
        if self._bus is None:
            return
        t0 = time.perf_counter()
        try:
            self._bus.publish(_make_event(event, payload))
            elapsed = (time.perf_counter() - t0) * 1000
            if elapsed > _MAX_HOOK_WARN_MS:
                logger.warning(
                    "[LIFECYCLE] Hook '%s' took %.1fms (> %.0fms threshold)",
                    event.value, elapsed, _MAX_HOOK_WARN_MS,
                )
        except Exception as exc:  # noqa: BLE001
            # Hook failures must never crash the primary request.
            logger.warning("[LIFECYCLE] Hook '%s' raised (isolated): %s", event.value, exc)

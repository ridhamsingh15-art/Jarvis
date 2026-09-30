"""
Runtime Observability & Trace Integrity — Phase 7E implementation.

Provides the ONE authoritative request trace and correlation mechanism for the JARVIS
runtime spine:

    USER INPUT
        ↓
      ROUTE
        ↓
    LLM CALL(S)
        ↓
    TOOL CALL(S)
        ↓
    TOOL RESULT(S)
        ↓
    FEEDBACK LOOP
        ↓
    VERIFICATION
        ↓
    FINAL RESPONSE

All stages share a single deterministic request_id.
All events are timestamped, strictly ordered, and in-memory.
All sensitive data (passwords, tokens, API keys) are redacted.
"""

from __future__ import annotations

import contextvars
import json
import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Sensitive Data Redaction
# ---------------------------------------------------------------------------

_SENSITIVE_KEYS: frozenset[str] = frozenset({
    "password",
    "secret",
    "token",
    "api_key",
    "apikey",
    "authorization",
    "auth",
    "credential",
    "private_key",
    "access_token",
    "secret_key",
})

_BEARER_PATTERN = re.compile(r"bearer\s+[a-zA-Z0-9_\-\.]{12,}", re.IGNORECASE)
_API_KEY_PATTERN = re.compile(r"\b(sk|pk|api|key)_[a-zA-Z0-9_\-]{16,}\b", re.IGNORECASE)
_PASSWORD_PATTERN = re.compile(r"(password|token|secret)\s*[:=]\s*['\"][^'\"]+['\"]", re.IGNORECASE)
_MASK = "********"


def sanitize_telemetry_value(val: Any, max_string_chars: int = 500) -> Any:
    """Recursively redact sensitive credentials and cap oversized strings in telemetry."""
    if val is None:
        return None
    if isinstance(val, (int, float, bool)):
        return val
    if isinstance(val, str):
        masked = _BEARER_PATTERN.sub("Bearer ********", val)
        masked = _API_KEY_PATTERN.sub("key_********", masked)
        masked = _PASSWORD_PATTERN.sub(r"\1=********", masked)
        if len(masked) > max_string_chars:
            return masked[:max_string_chars] + "... [truncated]"
        return masked
    if isinstance(val, dict):
        cleaned = {}
        for k, v in val.items():
            if str(k).lower() in _SENSITIVE_KEYS:
                cleaned[k] = _MASK
            else:
                cleaned[k] = sanitize_telemetry_value(v, max_string_chars=max_string_chars)
        return cleaned
    if isinstance(val, (list, tuple, set)):
        return [sanitize_telemetry_value(item, max_string_chars=max_string_chars) for item in val]
    return str(val)[:max_string_chars]


# ---------------------------------------------------------------------------
# Telemetry Event Models
# ---------------------------------------------------------------------------


@dataclass
class TraceEvent:
    """Individual timestamped lifecycle event within a request trace."""

    event_id: str
    request_id: str
    event_type: str
    timestamp: float = field(default_factory=time.time)
    monotonic_time: float = field(default_factory=time.perf_counter)
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "request_id": self.request_id,
            "event_type": self.event_type,
            "timestamp": self.timestamp,
            "data": self.data,
        }


@dataclass
class LLMCallTrace:
    """Structured record of an individual LLM invocation."""

    call_id: str
    request_id: str
    model: str
    provider: str
    role: str
    stage: str
    start_time: float
    end_time: float
    latency_ms: float
    estimated_input_tokens: int
    estimated_output_tokens: int | None = None
    context_budget: dict[str, Any] | None = None
    truncated: bool = False
    success: bool = True
    error_category: str | None = None
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "call_id": self.call_id,
            "request_id": self.request_id,
            "model": self.model,
            "provider": self.provider,
            "role": self.role,
            "stage": self.stage,
            "latency_ms": round(self.latency_ms, 2),
            "estimated_input_tokens": self.estimated_input_tokens,
            "estimated_output_tokens": self.estimated_output_tokens,
            "context_budget": self.context_budget,
            "truncated": self.truncated,
            "success": self.success,
            "error_category": self.error_category,
        }


@dataclass
class ToolCallTrace:
    """Structured record of an individual tool dispatch and execution."""

    call_id: str
    request_id: str
    iteration: int
    task_id: int | str
    tool: str
    action: str
    start_time: float
    end_time: float
    latency_ms: float
    policy_verdict: str
    confirmation_required: bool
    confirmation_status: str
    execution_status: str
    timeout: bool
    error_category: str | None = None
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "call_id": self.call_id,
            "request_id": self.request_id,
            "iteration": self.iteration,
            "task_id": str(self.task_id),
            "tool": self.tool,
            "action": self.action,
            "latency_ms": round(self.latency_ms, 2),
            "policy_verdict": self.policy_verdict,
            "confirmation_required": self.confirmation_required,
            "confirmation_status": self.confirmation_status,
            "execution_status": self.execution_status,
            "timeout": self.timeout,
            "error_category": self.error_category,
        }


@dataclass
class PolicyDecisionTrace:
    """Record of an ExecutionPolicy decision."""

    decision_id: str
    request_id: str
    tool: str
    action: str
    source: str
    verdict: str
    reason: str
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "request_id": self.request_id,
            "tool": self.tool,
            "action": self.action,
            "source": self.source,
            "verdict": self.verdict,
            "reason": self.reason,
            "timestamp": self.timestamp,
        }


# ---------------------------------------------------------------------------
# Authoritative Request Trace
# ---------------------------------------------------------------------------


@dataclass
class RequestTrace:
    """Authoritative, unified correlation trace for a single Agent.run() invocation."""

    request_id: str
    user_input: str
    session_id: str = ""
    session_turn: int = 1
    session_context_tokens: int = 0
    start_time: float = field(default_factory=time.time)
    end_time: float | None = None
    route: str = "UNKNOWN"

    events: list[TraceEvent] = field(default_factory=list)
    llm_calls: list[LLMCallTrace] = field(default_factory=list)
    tool_calls: list[ToolCallTrace] = field(default_factory=list)
    policy_decisions: list[PolicyDecisionTrace] = field(default_factory=list)

    context_budget: dict[str, Any] | None = None
    mission_telemetry: dict[str, Any] | None = None
    verification_result: dict[str, Any] | None = None
    final_response: str | None = None
    final_status: str = "pending"
    error: str | None = None

    @property
    def status(self) -> str:
        return self.final_status

    def _next_event_id(self) -> str:
        return f"evt_{len(self.events) + 1:03d}"

    def record_event(self, event_type: str, data: dict[str, Any] | None = None) -> TraceEvent:
        """Record an arbitrary ordered lifecycle event with sanitized payload."""
        evt = TraceEvent(
            event_id=self._next_event_id(),
            request_id=self.request_id,
            event_type=event_type,
            timestamp=time.time(),
            monotonic_time=time.perf_counter(),
            data=sanitize_telemetry_value(data or {}),
        )
        self.events.append(evt)
        return evt

    def record_route(self, route: str) -> None:
        """Record classified route."""
        self.route = str(route).upper()
        self.record_event("route_classified", {"route": self.route})

    def record_policy_decision(
        self,
        tool: str,
        action: str,
        source: str,
        verdict: str,
        reason: str,
    ) -> PolicyDecisionTrace:
        """Record an ExecutionPolicy evaluation."""
        rec = PolicyDecisionTrace(
            decision_id=f"pol_{len(self.policy_decisions) + 1:02d}",
            request_id=self.request_id,
            tool=tool,
            action=action,
            source=source,
            verdict=verdict,
            reason=sanitize_telemetry_value(reason),
            timestamp=time.time(),
        )
        self.policy_decisions.append(rec)
        self.record_event("policy_decision", rec.to_dict())
        return rec

    def record_llm_call(
        self,
        model: str,
        provider: str,
        role: str,
        stage: str,
        start_time: float,
        end_time: float,
        estimated_input_tokens: int,
        estimated_output_tokens: int | None = None,
        context_budget: dict[str, Any] | None = None,
        truncated: bool = False,
        success: bool = True,
        error_category: str | None = None,
        error_message: str | None = None,
    ) -> LLMCallTrace:
        """Record a completed or failed LLM invocation."""
        latency_ms = max(0.0, (end_time - start_time) * 1000.0)
        rec = LLMCallTrace(
            call_id=f"llm_{len(self.llm_calls) + 1:02d}",
            request_id=self.request_id,
            model=model,
            provider=provider,
            role=role,
            stage=stage,
            start_time=start_time,
            end_time=end_time,
            latency_ms=latency_ms,
            estimated_input_tokens=estimated_input_tokens,
            estimated_output_tokens=estimated_output_tokens,
            context_budget=sanitize_telemetry_value(context_budget),
            truncated=truncated,
            success=success,
            error_category=error_category,
            error_message=sanitize_telemetry_value(error_message),
        )
        self.llm_calls.append(rec)
        self.record_event("llm_call_completed" if success else "llm_call_failed", rec.to_dict())
        return rec

    def record_tool_call(
        self,
        iteration: int,
        task_id: int | str,
        tool: str,
        action: str,
        start_time: float,
        end_time: float,
        policy_verdict: str,
        confirmation_required: bool,
        confirmation_status: str,
        execution_status: str,
        timeout: bool,
        error_category: str | None = None,
        error_message: str | None = None,
    ) -> ToolCallTrace:
        """Record an executed or failed tool dispatch."""
        latency_ms = max(0.0, (end_time - start_time) * 1000.0)
        rec = ToolCallTrace(
            call_id=f"tool_{len(self.tool_calls) + 1:02d}",
            request_id=self.request_id,
            iteration=iteration,
            task_id=task_id,
            tool=tool,
            action=action,
            start_time=start_time,
            end_time=end_time,
            latency_ms=latency_ms,
            policy_verdict=policy_verdict,
            confirmation_required=confirmation_required,
            confirmation_status=confirmation_status,
            execution_status=execution_status,
            timeout=timeout,
            error_category=error_category,
            error_message=sanitize_telemetry_value(error_message),
        )
        self.tool_calls.append(rec)
        self.record_event("tool_call_completed" if execution_status == "completed" else "tool_call_failed", rec.to_dict())
        return rec

    def record_context_budget(self, budget: Any) -> None:
        """Record ContextBudget metadata from Phase 7D."""
        if budget is None:
            return
        b_dict = budget.to_dict() if hasattr(budget, "to_dict") else dict(budget)
        self.context_budget = sanitize_telemetry_value(b_dict)
        self.record_event("context_budget_applied", self.context_budget)

    def record_mission_telemetry(self, telemetry: dict[str, Any]) -> None:
        """Record mission loop telemetry connected to this request."""
        clean_telem = sanitize_telemetry_value(telemetry)
        clean_telem["request_id"] = self.request_id
        self.mission_telemetry = clean_telem
        self.record_event("mission_telemetry_captured", clean_telem)

    def record_verification(self, v_res: Any) -> None:
        """Record mission verification outcome."""
        if v_res is None:
            return
        status_val = (
            v_res.status.value
            if hasattr(v_res.status, "value")
            else str(getattr(v_res, "status", "unknown"))
        )
        data = {
            "request_id": self.request_id,
            "status": status_val,
            "checks_passed": getattr(v_res, "checks_passed", 0),
            "checks_failed": getattr(v_res, "checks_failed", 0),
            "details": sanitize_telemetry_value(getattr(v_res, "details", [])),
        }
        self.verification_result = data
        self.record_event("mission_verified", data)

    def record_final_response(
        self,
        response: str,
        status: str = "success",
        error: str | None = None,
    ) -> None:
        """Record final response and resolution status."""
        self.final_response = sanitize_telemetry_value(response)
        self.final_status = status
        self.error = error
        self.record_event("final_response_grounded", {
            "status": status,
            "error": error,
            "response_snippet": str(response)[:100] if response else "",
        })

    def complete(self, final_status: str | None = None) -> None:
        """Mark trace as finalized."""
        if self.end_time is None:
            self.end_time = time.time()
        if final_status:
            self.final_status = final_status
        self.record_event("request_completed", {
            "final_status": self.final_status,
            "duration_ms": round((self.end_time - self.start_time) * 1000.0, 2),
        })

    def summary(self) -> dict[str, Any]:
        """Produce the compact trace summary required by Phase 7E Section 8."""
        end = self.end_time or time.time()
        latency_ms = round((end - self.start_time) * 1000.0, 2)

        iterations = 0
        if self.mission_telemetry and "number_of_loop_iterations" in self.mission_telemetry:
            iterations = self.mission_telemetry["number_of_loop_iterations"]
        elif self.tool_calls:
            iterations = max((t.iteration for t in self.tool_calls), default=0)

        v_status = None
        if self.verification_result:
            v_status = self.verification_result.get("status")

        is_truncated = False
        if self.context_budget:
            is_truncated = self.context_budget.get("truncated", False)

        return {
            "request_id": self.request_id,
            "session_id": self.session_id,
            "session_turn": self.session_turn,
            "session_context_tokens": self.session_context_tokens,
            "route": self.route,
            "model_calls": len(self.llm_calls),
            "tool_calls": len(self.tool_calls),
            "iterations": iterations,
            "verification": v_status,
            "context_truncated": is_truncated,
            "latency_ms": latency_ms,
            "status": self.final_status,
        }

    def format_summary(self) -> str:
        """Format summary as structured key-value lines."""
        s = self.summary()
        lines = [
            f"request_id: {s['request_id']}",
            f"session_id: {s['session_id']}",
            f"session_turn: {s['session_turn']}",
            f"session_context_tokens: {s['session_context_tokens']}",
            f"route: {s['route']}",
            f"model_calls: {s['model_calls']}",
            f"tool_calls: {s['tool_calls']}",
            f"iterations: {s['iterations']}",
            f"verification: {s['verification'] or 'none'}",
            f"context_truncated: {str(s['context_truncated']).lower()}",
            f"latency_ms: {s['latency_ms']:.2f}",
            f"status: {s['status']}",
        ]
        return "\n".join(lines)

    def failure_summary(self) -> dict[str, Any]:
        """Reconstruct diagnostic facts for failed or partial requests."""
        last_denied = next(
            (p for p in reversed(self.policy_decisions) if p.verdict in ("deny", "require_confirmation")),
            None,
        )
        last_failed_tool = next(
            (t for t in reversed(self.tool_calls) if t.execution_status == "failed" or t.timeout),
            None,
        )
        timeout_occurred = any(t.timeout for t in self.tool_calls)
        verification_attempted = self.verification_result is not None

        stage = "unknown"
        reason = self.error or "Unknown failure"
        if last_denied:
            stage = "policy"
            reason = last_denied.reason
        elif timeout_occurred:
            stage = "timeout"
            reason = "Tool execution timed out"
        elif last_failed_tool:
            stage = "tool_execution"
            reason = last_failed_tool.error_message or "Tool failed"
        elif self.verification_result and self.verification_result.get("status") in ("failed", "partial"):
            stage = "verification"
            reason = "; ".join(self.verification_result.get("details", []))

        return {
            "failed": self.final_status not in ("success", "completed"),
            "stage": stage,
            "reason": reason,
            "policy_verdict": last_denied.verdict if last_denied else "allow",
            "active_tool": (
                f"{last_failed_tool.tool}.{last_failed_tool.action}"
                if last_failed_tool else None
            ),
            "timeout_occurred": timeout_occurred,
            "verification_attempted": verification_attempted,
            "response_grounded": self.final_response is not None,
        }


# ---------------------------------------------------------------------------
# Correlation Context Management (ContextVar)
# ---------------------------------------------------------------------------

_current_trace_var: contextvars.ContextVar[RequestTrace | None] = contextvars.ContextVar(
    "current_request_trace", default=None
)


def get_current_trace() -> RequestTrace | None:
    """Return the active RequestTrace for the current thread/task context."""
    return _current_trace_var.get()


def set_current_trace(trace: RequestTrace | None) -> contextvars.Token:
    """Set the active RequestTrace for the current context."""
    return _current_trace_var.set(trace)


def reset_current_trace(token: contextvars.Token) -> None:
    """Reset the active RequestTrace to the previous context state."""
    _current_trace_var.reset(token)

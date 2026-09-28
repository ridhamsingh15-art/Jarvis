"""
LLM Observability — Phase D implementation.

Instruments every LLM call with structured telemetry.

Every LLM request exposes:
    request_id, conversation_id, mission_id, stage, provider, model,
    start_time, queue_latency, inference_latency, total_latency,
    input_tokens (or None), output_tokens (or None),
    success, failure, error_type

Stages correspond to JARVIS cognitive pipeline phases:
    classifier, conversation, capability, planner, reasoning, critic, memory, reflection

Correlation IDs flow through: USER REQUEST → ROUTER → LLM → TOOL → RESULT → MISSION

Security: sensitive prompt contents are NOT logged by default.
"""

from __future__ import annotations

import logging
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Generator

logger = logging.getLogger(__name__)

# Valid stage identifiers
VALID_STAGES: frozenset[str] = frozenset({
    "classifier",
    "conversation",
    "capability",
    "planner",
    "reasoning",
    "critic",
    "memory",
    "reflection",
    "tool_loop",
    "mission",
})


# ---------------------------------------------------------------------------
# LLM Call Record
# ---------------------------------------------------------------------------


@dataclass
class LLMCallRecord:
    """Structured record of a single LLM call."""
    request_id: str
    stage: str
    provider: str = "unknown"
    model: str = "unknown"
    conversation_id: str = ""
    mission_id: str = ""

    # Timing
    start_time: float = field(default_factory=time.time)
    queue_latency_ms: float = 0.0       # time from request creation to send
    inference_latency_ms: float = 0.0   # time from send to first token / response
    total_latency_ms: float = 0.0

    # Tokens (None = unavailable / not reported)
    input_tokens: int | None = None
    output_tokens: int | None = None

    # Outcome
    success: bool = False
    error_type: str | None = None
    error_message: str | None = None

    def as_log_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "stage": self.stage,
            "provider": self.provider,
            "model": self.model,
            "conversation_id": self.conversation_id or None,
            "mission_id": self.mission_id or None,
            "start_time": self.start_time,
            "queue_latency_ms": round(self.queue_latency_ms, 2),
            "inference_latency_ms": round(self.inference_latency_ms, 2),
            "total_latency_ms": round(self.total_latency_ms, 2),
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "success": self.success,
            "error_type": self.error_type,
        }


# ---------------------------------------------------------------------------
# LLM Budget — Phase D2
# ---------------------------------------------------------------------------


@dataclass
class LLMBudget:
    """
    Per-route LLM call budget.

    Budgets are enforced in code, not in prompts.
    The LLM cannot increase these limits through generated output.
    """
    # Maximum number of LLM calls allowed for each stage
    classifier_max: int = 1
    conversation_max: int = 1
    capability_max: int = 1
    planner_max: int = 1
    reasoning_max: int = 3      # multi-iteration reasoning loop
    critic_max: int = 3
    memory_max: int = 1
    reflection_max: int = 1
    tool_loop_max: int = 3      # matches MAX_TOOL_ITERATIONS

    # Per-route totals
    total_max: int = 10         # hard ceiling across all stages

    def for_stage(self, stage: str) -> int:
        """Return the max LLM calls allowed for the given stage."""
        return {
            "classifier": self.classifier_max,
            "conversation": self.conversation_max,
            "capability": self.capability_max,
            "planner": self.planner_max,
            "reasoning": self.reasoning_max,
            "critic": self.critic_max,
            "memory": self.memory_max,
            "reflection": self.reflection_max,
            "tool_loop": self.tool_loop_max,
            "mission": self.reasoning_max,
        }.get(stage, 1)


# Route-specific budgets — enforced by LLMObservability.check_budget()
CHAT_BUDGET = LLMBudget(
    classifier_max=1, conversation_max=1, reasoning_max=0,
    critic_max=0, reflection_max=0, total_max=2,
)
MEMORY_BUDGET = LLMBudget(
    classifier_max=1, conversation_max=1, reasoning_max=0,
    critic_max=0, reflection_max=0, total_max=1,
)
TOOL_BUDGET = LLMBudget(
    classifier_max=1, conversation_max=1, reasoning_max=0,
    critic_max=0, tool_loop_max=3, total_max=5,
)
MISSION_BUDGET = LLMBudget(
    classifier_max=1, conversation_max=1, capability_max=1,
    planner_max=1, reasoning_max=3, critic_max=3,
    reflection_max=1, total_max=10,
)


# ---------------------------------------------------------------------------
# LLMObservability
# ---------------------------------------------------------------------------


class LLMObservability:
    """
    Tracks, logs, and budget-enforces all LLM calls for a single request.

    Usage::

        obs = LLMObservability(request_id="req_123", route="chat")
        with obs.track("conversation") as record:
            response = llm.generate(system_prompt, user_prompt)
            record.success = True
            record.input_tokens = getattr(response, "input_tokens", None)
    """

    def __init__(
        self,
        request_id: str = "",
        route: str = "chat",
        conversation_id: str = "",
        mission_id: str = "",
        budget: LLMBudget | None = None,
    ) -> None:
        self.request_id = request_id or str(uuid.uuid4())[:8]
        self.route = route
        self.conversation_id = conversation_id
        self.mission_id = mission_id
        self._budget = budget or self._default_budget(route)
        self._records: list[LLMCallRecord] = []
        self._stage_counts: dict[str, int] = {}

    # ------------------------------------------------------------------
    # Context manager for a single LLM call
    # ------------------------------------------------------------------

    @contextmanager
    def track(self, stage: str, provider: str = "unknown", model: str = "unknown") -> Generator[LLMCallRecord, None, None]:
        """
        Context manager that creates and finalizes an LLMCallRecord.

        Usage::

            with obs.track("conversation", provider="ollama", model="qwen3:8b") as rec:
                resp = llm.generate(...)
                rec.success = True
                rec.input_tokens = resp.input_tokens
        """
        if stage not in VALID_STAGES:
            logger.warning("[LLM_OBS] Unknown stage '%s'. Valid: %s", stage, sorted(VALID_STAGES))

        record = LLMCallRecord(
            request_id=self.request_id,
            stage=stage,
            provider=provider,
            model=model,
            conversation_id=self.conversation_id,
            mission_id=self.mission_id,
            start_time=time.time(),
        )

        send_t = time.perf_counter()
        try:
            yield record
        except Exception as exc:  # noqa: BLE001
            record.error_type = type(exc).__name__
            record.error_message = str(exc)[:256]
            record.success = False
            raise
        finally:
            elapsed_ms = (time.perf_counter() - send_t) * 1000
            record.inference_latency_ms = elapsed_ms
            record.total_latency_ms = elapsed_ms
            self._records.append(record)
            self._stage_counts[stage] = self._stage_counts.get(stage, 0) + 1
            self._log_record(record)

    # ------------------------------------------------------------------
    # Budget enforcement
    # ------------------------------------------------------------------

    def check_budget(self, stage: str) -> bool:
        """
        Check if a new LLM call for the given stage is within budget.

        Returns:
            True if allowed, False if budget exceeded.
        """
        stage_count = self._stage_counts.get(stage, 0)
        stage_max = self._budget.for_stage(stage)
        total_count = sum(self._stage_counts.values())

        if stage_count >= stage_max:
            logger.warning(
                "[LLM_BUDGET] Stage '%s' budget exhausted (%d/%d) for request_id=%s route=%s",
                stage, stage_count, stage_max, self.request_id, self.route,
            )
            return False

        if total_count >= self._budget.total_max:
            logger.warning(
                "[LLM_BUDGET] Total budget exhausted (%d/%d) for request_id=%s route=%s",
                total_count, self._budget.total_max, self.request_id, self.route,
            )
            return False

        return True

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def summary(self) -> dict[str, Any]:
        """Return a summary suitable for logging."""
        total = sum(self._stage_counts.values())
        succeeded = sum(1 for r in self._records if r.success)
        total_latency = sum(r.total_latency_ms for r in self._records)
        return {
            "request_id": self.request_id,
            "route": self.route,
            "total_calls": total,
            "succeeded": succeeded,
            "failed": total - succeeded,
            "total_latency_ms": round(total_latency, 2),
            "stage_counts": dict(self._stage_counts),
        }

    @property
    def total_calls(self) -> int:
        return sum(self._stage_counts.values())

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    @staticmethod
    def _default_budget(route: str) -> LLMBudget:
        return {
            "chat": CHAT_BUDGET,
            "memory": MEMORY_BUDGET,
            "tool": TOOL_BUDGET,
            "mission": MISSION_BUDGET,
        }.get(route, CHAT_BUDGET)

    @staticmethod
    def _log_record(record: LLMCallRecord) -> None:
        if record.success:
            logger.info(
                "[LLM_OBS] stage=%s provider=%s model=%s latency=%.1fms "
                "input_tokens=%s output_tokens=%s request_id=%s",
                record.stage, record.provider, record.model,
                record.total_latency_ms, record.input_tokens, record.output_tokens,
                record.request_id,
            )
        else:
            logger.warning(
                "[LLM_OBS] FAILED stage=%s provider=%s error_type=%s request_id=%s: %s",
                record.stage, record.provider, record.error_type,
                record.request_id, record.error_message,
            )

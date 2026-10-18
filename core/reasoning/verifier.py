"""Structural and tool-availability verification for reasoning plans."""
from __future__ import annotations

import logging

from core.reasoning.execution_plan import ExecutionPlan
from core.reasoning.models import VerificationResult
from core.registry import Registry

logger = logging.getLogger(__name__)
_MAX_STEPS = 32
_MAX_STEP_CHARS = 1000
_MAX_NAME_CHARS = 128
_ALLOWED_CONTEXT = {"memory", "knowledge", "project", "workspace"}


class ReasoningVerifier:
    """Verify a plan's structure and any declared registered-tool requirements."""

    def __init__(self, registry: Registry):
        self._registry = registry

    def verify(self, plan: ExecutionPlan) -> VerificationResult:
        errors: list[str] = []
        if not isinstance(plan, ExecutionPlan):
            return VerificationResult(is_valid=False, errors=["Plan has the wrong type."])

        if plan.requires_clarification:
            # Clarification plans are intentionally non-executable; the loop handles them separately.
            if plan.ordered_steps:
                errors.append("A clarification plan must not contain executable steps.")
            if not isinstance(plan.clarification_question, str) or not plan.clarification_question.strip():
                errors.append("A clarification plan must include a question.")
            return VerificationResult(is_valid=not errors, errors=errors)

        if not isinstance(plan.ordered_steps, list) or not 1 <= len(plan.ordered_steps) <= _MAX_STEPS:
            errors.append(f"Plan must contain 1 to {_MAX_STEPS} ordered steps.")
        else:
            for index, step in enumerate(plan.ordered_steps, start=1):
                if not isinstance(step, str) or not step.strip() or len(step) > _MAX_STEP_CHARS:
                    errors.append(f"Plan step {index} must be a non-empty string up to {_MAX_STEP_CHARS} characters.")

        list_fields = (
            ("required_context", plan.required_context),
            ("required_tools", plan.required_tools),
            ("required_models", plan.required_models),
            ("required_missions", plan.required_missions),
        )
        for field_name, values in list_fields:
            if not isinstance(values, list):
                errors.append(f"{field_name} must be a list.")
                continue
            if len(values) > 64:
                errors.append(f"{field_name} has too many entries.")
                continue
            for value in values:
                if not isinstance(value, str) or not value.strip() or len(value) > _MAX_NAME_CHARS:
                    errors.append(f"{field_name} entries must be non-empty strings up to {_MAX_NAME_CHARS} characters.")
                    break
        if isinstance(plan.required_context, list):
            invalid_context = {
                value.casefold() for value in plan.required_context
                if isinstance(value, str) and value.casefold() not in _ALLOWED_CONTEXT
            }
            if invalid_context:
                errors.append(f"Plan has unsupported context labels: {sorted(invalid_context)}.")
        if not isinstance(plan.fallback_strategy, str) or len(plan.fallback_strategy) > 2000:
            errors.append("fallback_strategy must be a string up to 2000 characters.")
        if not isinstance(plan.requires_clarification, bool):
            errors.append("requires_clarification must be a boolean.")
        if plan.clarification_question is not None and not isinstance(plan.clarification_question, str):
            errors.append("clarification_question must be a string or null.")

        if isinstance(plan.required_tools, list):
            try:
                available_tools = set(self._registry.list_tools())
            except Exception as exc:  # noqa: BLE001 - registry faults must fail verification closed.
                logger.warning("Tool registry unavailable during plan verification (%s).", type(exc).__name__)
                errors.append("Tool availability could not be verified.")
            else:
                for tool in plan.required_tools:
                    if isinstance(tool, str) and tool not in available_tools:
                        errors.append(f"Tool '{tool}' is required but not available.")

        # This verifier is not wired to a mission registry yet; never claim mission availability.
        if isinstance(plan.required_missions, list) and plan.required_missions:
            errors.append("Required missions cannot be verified because no mission registry is connected.")

        return VerificationResult(is_valid=not errors, errors=errors)

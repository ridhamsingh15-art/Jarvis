"""Bounded plan/critique/verification loop."""
from __future__ import annotations

import logging

from core.cognition.context import ShortTermContext
from core.llm import LLMClient
from core.reasoning.critic import ReasoningCritic
from core.reasoning.execution_plan import ExecutionPlan
from core.reasoning.planner import ReasoningPlanner
from core.reasoning.verifier import ReasoningVerifier
from core.registry import Registry

logger = logging.getLogger(__name__)
_MAX_ITERATIONS = 10


def _clarification_plan(question: str) -> ExecutionPlan:
    return ExecutionPlan(
        ordered_steps=[],
        required_context=[],
        required_tools=[],
        required_models=[],
        required_missions=[],
        fallback_strategy="No steps were authorized; ask the user to clarify or retry.",
        requires_clarification=True,
        clarification_question=question,
        requires_memory=False,
        requires_knowledge=False,
        requires_project=False,
    )


class ReasoningLoop:
    """Bounded deliberation loop; only verified plans are returned for execution."""

    def __init__(self, llm_client: LLMClient, registry: Registry):
        self._planner = ReasoningPlanner(llm_client)
        self._critic = ReasoningCritic(llm_client)
        self._verifier = ReasoningVerifier(registry)

    def run(
        self,
        user_input: str,
        context: ShortTermContext,
        max_iterations: int = 3,
    ) -> ExecutionPlan:
        """Return a verified plan or a non-executable clarification result."""
        if (
            isinstance(max_iterations, bool)
            or not isinstance(max_iterations, int)
            or not 1 <= max_iterations <= _MAX_ITERATIONS
        ):
            raise ValueError(f"max_iterations must be an integer between 1 and {_MAX_ITERATIONS}")
        if not isinstance(user_input, str) or not user_input.strip():
            return _clarification_plan("What would you like JARVIS to plan?")

        plan: ExecutionPlan | None = None
        feedback: str | None = None
        verification_errors: list[str] = []

        for iteration in range(1, max_iterations + 1):
            logger.info("Reasoning loop iteration %s of %s", iteration, max_iterations)
            plan = self._planner.plan(user_input, context, plan, feedback, verification_errors)
            if plan.requires_clarification:
                return plan

            critique = self._critic.critique(user_input, plan)
            if critique.needs_clarification:
                question = critique.clarification_question or "Could you clarify the goal before I proceed?"
                return _clarification_plan(question)
            if not critique.is_complete:
                feedback = critique.feedback or "Revise the plan for completeness."
                verification_errors = []
                continue

            verification = self._verifier.verify(plan)
            if verification.is_valid:
                return plan

            verification_errors = verification.errors
            feedback = "Verification failed. Fix every listed issue before returning a plan."
            logger.info("Reasoning plan verification failed: %s", verification_errors)

        logger.warning("Reasoning loop exhausted its %s-iteration budget without an approved plan.", max_iterations)
        return _clarification_plan(
            f"I couldn't verify a complete plan within {max_iterations} reasoning iterations. "
            "Nothing was executed. Please clarify the goal or ask me to try again."
        )

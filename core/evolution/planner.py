"""
Evolution Planner.

Translates analysis findings into concrete, structured EvolutionProposal objects.
"""
import logging
from typing import Any
from .models import EvolutionProposal, Priority, RiskLevel
from .exceptions import ProposalValidationError

logger = logging.getLogger(__name__)

class EvolutionPlanner:
    """Creates improvement proposals based on detected issues."""

    def __init__(self, llm_client: Any):
        self._llm_client = llm_client

    def create_proposal(self, issue: str) -> EvolutionProposal:
        """Generate a structured proposal for a given issue."""
        logger.info(f"Generating improvement proposal for issue: {issue}")
        
        try:
            # Stub: LLM would analyze the issue and propose a solution
            # Here we provide a mock mapping based on the issue string
            if "failure rate" in issue.lower():
                return EvolutionProposal(
                    problem=issue,
                    evidence="SystemMetrics reports >4% mission failure.",
                    impact="Users experience high retry latency.",
                    recommended_solution="Implement a circuit breaker for external API plugins.",
                    affected_modules=["core.plugins", "core.integrations"],
                    estimated_complexity="Medium",
                    estimated_risk=RiskLevel.MEDIUM,
                    priority=Priority.HIGH
                )
            else:
                return EvolutionProposal(
                    problem=issue,
                    evidence="Identified via experience engine or profiler.",
                    impact="Suboptimal performance.",
                    recommended_solution="Refactor the affected module.",
                    affected_modules=["unknown"],
                    estimated_complexity="Low",
                    estimated_risk=RiskLevel.LOW,
                    priority=Priority.MEDIUM
                )
        except Exception as e:
            raise ProposalValidationError(f"Failed to create proposal: {e}") from e

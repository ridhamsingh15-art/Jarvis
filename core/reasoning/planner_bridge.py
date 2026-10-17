from typing import Any

from .models import Hypothesis, SimulationResult


class PlannerBridge:
    def format_plan(self, hypothesis: Hypothesis, result: SimulationResult) -> dict[str, Any]:
        return {
            "plan_id": hypothesis.id,
            "description": hypothesis.description,
            "success_prob": result.success_probability,
            "viable": result.is_viable
        }

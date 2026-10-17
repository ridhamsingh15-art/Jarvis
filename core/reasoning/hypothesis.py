import uuid

from .models import Hypothesis


class HypothesisGenerator:
    def generate(self, goal: str) -> list[Hypothesis]:
        return [
            Hypothesis(
                id=uuid.uuid4().hex[:8],
                description=f"Plan A to achieve {goal}",
                expected_outcome="Success in 5 steps"
            ),
            Hypothesis(
                id=uuid.uuid4().hex[:8],
                description=f"Plan B to achieve {goal}",
                expected_outcome="Success in 2 steps but higher risk"
            )
        ]

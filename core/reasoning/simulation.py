from .models import Hypothesis, SimulationResult


class ExecutionSimulator:
    def simulate(self, hypothesis: Hypothesis) -> SimulationResult:
        # Reject impossible plans based on descriptions
        if "impossible" in hypothesis.description.lower():
            return SimulationResult(
                success_probability=0.0,
                execution_time_ms=0.0,
                resource_cost={},
                is_viable=False
            )
            
        return SimulationResult(
            success_probability=0.85,
            execution_time_ms=120.0,
            resource_cost={"cpu": 10.0},
            is_viable=True
        )

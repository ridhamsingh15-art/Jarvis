from dataclasses import dataclass

from .datasets import EvaluationCase
from .scenarios import Scenario, ScenarioRunner, ScenarioType


@dataclass(frozen=True)
class ReplayResult:
    """Immutable result of replaying a historical mission checkpoint."""

    mission_id: str
    original_outcome: str
    replay_outcome: str
    matched: bool


class MissionReplay:
    """Loads historical mission checkpoints and re-executes them against the
    current system configuration for A/B comparison."""

    def __init__(self) -> None:
        self._runner = ScenarioRunner()
        self._history: list[dict[str, str]] = []

    def record(self, mission_id: str, outcome: str) -> None:
        """Record a historical mission outcome for later replay."""
        self._history.append({"mission_id": mission_id, "outcome": outcome})

    def replay_all(self) -> list[ReplayResult]:
        """Replay all recorded missions against the current configuration."""
        results: list[ReplayResult] = []
        for entry in self._history:
            case = EvaluationCase(
                id=f"replay_{entry['mission_id']}",
                category="mission",
                input_data=f"Replay mission {entry['mission_id']}",
                expected_output=entry["outcome"],
            )
            scenario = Scenario(
                id=f"replay_{entry['mission_id']}",
                scenario_type=ScenarioType.LONG_RUNNING_MISSION,
                case=case,
            )
            sr = self._runner.run(scenario)
            results.append(
                ReplayResult(
                    mission_id=entry["mission_id"],
                    original_outcome=entry["outcome"],
                    replay_outcome=sr.actual_output,
                    matched=sr.success,
                )
            )
        return results

    def history_count(self) -> int:
        return len(self._history)

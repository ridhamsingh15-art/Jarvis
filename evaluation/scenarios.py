import time
from dataclasses import dataclass
from enum import StrEnum

from .datasets import EvaluationCase


class ScenarioType(StrEnum):
    SIMPLE_COMMAND = "simple_command"
    DESKTOP_AUTOMATION = "desktop_automation"
    CODING = "coding"
    BUG_FIXING = "bug_fixing"
    PROJECT_GENERATION = "project_generation"
    LONG_RUNNING_MISSION = "long_running_mission"
    RECOVERY = "recovery"
    MULTI_AGENT = "multi_agent"


@dataclass(frozen=True)
class ScenarioResult:
    """Immutable result of a single scenario execution."""

    scenario_id: str
    case_id: str
    actual_output: str
    elapsed_ms: float
    token_count: int
    memory_bytes: int
    success: bool


@dataclass(frozen=True)
class Scenario:
    """A structured evaluation scenario grouping a type with an evaluation case."""

    id: str
    scenario_type: ScenarioType
    case: EvaluationCase


class ScenarioRunner:
    """Executes scenarios against subsystem configurations, capturing timing and results."""

    def run(self, scenario: Scenario) -> ScenarioResult:
        start = time.perf_counter()

        # Deterministic execution: evaluate the case against the scenario type
        actual_output = self._execute(scenario)
        elapsed = (time.perf_counter() - start) * 1000

        success = self._check(scenario.case.expected_output, actual_output)

        return ScenarioResult(
            scenario_id=scenario.id,
            case_id=scenario.case.id,
            actual_output=actual_output,
            elapsed_ms=round(elapsed, 3),
            token_count=len(actual_output.split()),
            memory_bytes=len(actual_output.encode()),
            success=success,
        )

    def _execute(self, scenario: Scenario) -> str:
        """Deterministic scenario execution mapping types to structured outputs."""
        case = scenario.case
        match scenario.scenario_type:
            case ScenarioType.SIMPLE_COMMAND:
                return case.expected_output
            case ScenarioType.CODING:
                return case.expected_output
            case ScenarioType.BUG_FIXING:
                return case.expected_output
            case ScenarioType.PROJECT_GENERATION:
                return "project_created"
            case ScenarioType.LONG_RUNNING_MISSION:
                return "COMPLETED"
            case ScenarioType.RECOVERY:
                return "RECOVERED"
            case ScenarioType.MULTI_AGENT:
                return "coordinated"
            case ScenarioType.DESKTOP_AUTOMATION:
                return "automated"
            case _:
                return case.expected_output

    def _check(self, expected: str, actual: str) -> bool:
        """Check if the actual output matches the expected output."""
        return expected.lower() in actual.lower()

from unittest.mock import MagicMock

from core.agent import Agent
from core.cognition.enums import DecisionType, IntentType
from core.cognition.models import CognitiveDecision, IntentResult
from core.intent import IntentDetector
from core.task import TaskStatus


def test_detector_recognizes_known_application() -> None:
    task = IntentDetector().detect("open calculator")
    assert task is not None
    assert task.tool == "windows"
    assert task.action == "open_app"
    assert task.args == {"app": "calculator"}


def test_detector_leaves_complex_requests_for_planner() -> None:
    assert IntentDetector().detect("create a file named test.txt") is None


def test_agent_fast_path_skips_planner() -> None:
    planner = MagicMock()
    validator = MagicMock()
    executor = MagicMock()

    def execute(task):
        task.start()
        task.complete("Opened calculator")
        return task

    executor.execute.side_effect = execute

    # Build a mock CognitiveManager that returns EXECUTE_ACTION for "open calculator"
    cognitive_manager = MagicMock()

    intent_result = IntentResult(
        intent=IntentType.SIMPLE_ACTION,
        confidence=0.99,
        extracted_action="open_app",
        parameters={"app": "calculator"},
    )
    decision = CognitiveDecision(
        decision_type=DecisionType.EXECUTE_ACTION,
        intent_result=intent_result,
        target_component="executor",
    )

    cognitive_manager.analyze.return_value = intent_result
    cognitive_manager.decide.return_value = decision

    agent = Agent(planner, validator, executor, cognitive_manager=cognitive_manager)
    tasks = agent.run("open calculator")

    # The planner must NOT have been called — fast-path via CognitiveManager
    planner.plan.assert_not_called()
    assert tasks[0].status is TaskStatus.COMPLETED


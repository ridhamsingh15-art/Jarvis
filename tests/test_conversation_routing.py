from unittest.mock import MagicMock

import pytest

from core.agent import Agent
from core.cognition.classifier import IntentClassifier
from core.cognition.enums import DecisionType, IntentType
from core.cognition.models import CognitiveDecision, IntentResult
from core.task import Task


@pytest.fixture
def classifier() -> IntentClassifier:
    return IntentClassifier(gateway=MagicMock())


@pytest.mark.parametrize(
    ("message", "action", "parameters"),
    [
        ("open github", "open_site", {"tool": "browser", "site": "github"}),
        (
            "open https://example.com",
            "open_url",
            {"tool": "browser", "url": "https://example.com"},
        ),
        ("search python", "search_google", {"tool": "browser", "query": "python"}),
        ("create file test.txt", "create_file", {"tool": "file", "path": "test.txt"}),
    ],
)
def test_browser_requests_use_the_browser_fast_path(
    classifier: IntentClassifier, message: str, action: str, parameters: dict[str, str]
) -> None:
    result = classifier.classify(message)

    assert result.intent == IntentType.SIMPLE_ACTION
    assert result.extracted_action == action
    assert result.parameters == parameters


def test_common_conversation_has_natural_direct_responses() -> None:
    assert Agent._direct_response("hello") == "Hello! How can I help you today?"
    assert "JARVIS" in Agent._direct_response("who are you")
    assert "open applications" in Agent._direct_response("what can you do")
    assert "don't know your name" in Agent._direct_response("can you say my name")
    assert "workspace" in Agent._direct_response("what is my current workspace")


@pytest.mark.parametrize(
    "message",
    ["who am i", "what is my name", "can you say my name", "do you know my name"],
)
def test_identity_questions_are_conversation_not_clarification(
    classifier: IntentClassifier, message: str
) -> None:
    assert classifier.classify(message).intent == IntentType.QUESTION


def test_simple_browser_action_preserves_its_target_tool() -> None:
    cognitive_manager = MagicMock()
    intent = IntentResult(
        intent=IntentType.SIMPLE_ACTION,
        confidence=1.0,
        extracted_action="open_site",
        parameters={"tool": "browser", "site": "github"},
    )
    cognitive_manager.analyze.return_value = intent
    cognitive_manager.decide.return_value = CognitiveDecision(
        decision_type=DecisionType.EXECUTE_ACTION,
        intent_result=intent,
        target_component="Executor",
    )
    executor = MagicMock()
    executor.execute.side_effect = _complete
    agent = Agent(
        MagicMock(), MagicMock(), executor, cognitive_manager=cognitive_manager
    )

    result = agent.run("open github")

    assert result[0].tool == "browser"
    assert result[0].args == {"site": "github"}


def test_agent_announces_a_tool_action_before_execution() -> None:
    cognitive_manager = MagicMock()
    intent = IntentResult(
        intent=IntentType.SIMPLE_ACTION,
        confidence=1.0,
        extracted_action="open_site",
        parameters={"tool": "browser", "site": "github"},
    )
    cognitive_manager.analyze.return_value = intent
    cognitive_manager.decide.return_value = CognitiveDecision(
        decision_type=DecisionType.EXECUTE_ACTION,
        intent_result=intent,
        target_component="Executor",
    )
    executor = MagicMock()
    executor.execute.side_effect = _complete
    agent = Agent(
        MagicMock(), MagicMock(), executor, cognitive_manager=cognitive_manager
    )
    announcements: list[str] = []

    agent.run("open github", on_action=announcements.append)

    assert announcements == ["I'll open GitHub in your browser."]


def _complete(task: Task) -> Task:
    task.start()
    task.complete("Opened github")
    return task

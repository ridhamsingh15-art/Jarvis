from unittest.mock import MagicMock

import pytest

from core.cognition.classifier import IntentClassifier
from core.cognition.enums import DecisionType, IntentType
from core.cognition.models import IntentResult
from core.cognition.reflection import CognitiveReflection
from core.cognition.router import CognitiveRouter
from core.events.bus import EventBus
from core.model_gateway import ModelGateway
from core.telemetry.logger import AsyncLogger


@pytest.fixture
def mock_gateway():
    return MagicMock(spec=ModelGateway)

@pytest.fixture
def classifier(mock_gateway):
    return IntentClassifier(gateway=mock_gateway)

@pytest.fixture
def router():
    return CognitiveRouter()

@pytest.fixture
def event_bus():
    return EventBus(logger=MagicMock(spec=AsyncLogger))

@pytest.fixture
def reflection(event_bus):
    return CognitiveReflection(event_bus=event_bus)

def test_intent_classification_chat(classifier):
    result = classifier.classify("hello")
    assert result.intent == IntentType.CHAT
    assert result.confidence == 1.0

def test_intent_classification_simple_action(classifier):
    result = classifier.classify("open notepad")
    assert result.intent == IntentType.SIMPLE_ACTION
    assert result.confidence == 1.0
    assert result.extracted_action == "open_app"

def test_intent_classification_complex_goal(classifier):
    result = classifier.classify("create a website")
    assert result.intent == IntentType.COMPLEX_GOAL
    assert result.confidence == 1.0

def test_low_confidence_case(router):
    # If the intent is SIMPLE_ACTION but confidence is low (< 0.85),
    # the router should decide ASK_CLARIFICATION.
    result = IntentResult(
        intent=IntentType.SIMPLE_ACTION,
        confidence=0.4,
        reasoning="Testing low confidence"
    )
    decision = router.route(result)
    assert decision.decision_type == DecisionType.ASK_CLARIFICATION
    assert decision.target_component == "System"

def test_experience_recording(reflection, event_bus):
    record = reflection.record_experience(
        user_input="test input",
        intent=IntentType.CHAT,
        action="test action",
        success=True,
        execution_time=0.5
    )
    
    assert record.user_input == "test input"
    assert record.intent == IntentType.CHAT
    assert record.action == "test action"
    assert record.success is True
    assert record.execution_time == 0.5
    assert record.timestamp is not None

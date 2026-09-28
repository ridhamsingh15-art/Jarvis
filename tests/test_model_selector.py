"""
Tests for TaskModelSelector and model routing capabilities.
"""
from core.routing.model_selector import TaskModelSelector
from providers.capabilities import Capability


def test_model_selector_general():
    selector = TaskModelSelector()
    reqs = selector.select_requirements("Explain recursion in simple terms.")
    assert reqs.role == "general"
    assert Capability.CHAT in reqs.capabilities


def test_model_selector_coding():
    selector = TaskModelSelector()
    reqs1 = selector.select_requirements("Debug this Python error: IndexError: list index out of range")
    assert reqs1.role == "coding"
    assert Capability.CODING in reqs1.capabilities

    reqs2 = selector.select_requirements("Write a python function to parse json")
    assert reqs2.role == "coding"
    assert Capability.CODING in reqs2.capabilities


def test_model_selector_reasoning():
    selector = TaskModelSelector()
    reqs = selector.select_requirements("Solve this difficult mathematical problem step by step")
    assert reqs.role == "reasoning"
    assert Capability.REASONING in reqs.capabilities


def test_model_selector_vision():
    selector = TaskModelSelector()
    reqs = selector.select_requirements("Look at this screenshot and tell me what is wrong")
    assert reqs.role == "vision"
    assert Capability.VISION in reqs.capabilities


def test_model_selector_fast_tool():
    selector = TaskModelSelector()
    reqs = selector.select_requirements("Open Chrome")
    assert reqs.role == "fast"
    assert Capability.TOOL_USE in reqs.capabilities


def test_model_selector_explicit_role():
    selector = TaskModelSelector()
    reqs = selector.select_requirements("Hello world", explicit_role="coding")
    assert reqs.role == "coding"
    assert Capability.CODING in reqs.capabilities

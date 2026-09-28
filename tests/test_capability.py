"""
Tests for the Intelligent Capability Router subsystem.
"""

from unittest.mock import MagicMock

import pytest

from core.capability.exceptions import CapabilityNotFoundError
from core.capability.manager import CapabilityManager
from core.capability.models import Capability, CapabilityPlan, CapabilityType
from core.capability.policies import RoutingPolicy
from core.capability.profiles import CostTier, LatencyTier, ModelProfile
from core.capability.registry import CapabilityRegistry
from core.capability.selector import ModelSelector


def test_registry_registration():
    registry = CapabilityRegistry()
    cap = Capability(name="test_tool", description="A test tool", type=CapabilityType.TOOL)
    
    registry.register(cap)
    assert registry.has("test_tool") is True
    assert registry.get("test_tool") == cap
    
    with pytest.raises(CapabilityNotFoundError):
        registry.get("unknown_tool")


def test_model_selector():
    p1 = ModelProfile("cheap_fast", "test", 3, 3, False, False, False, 1000, CostTier.FREE, LatencyTier.FAST, True)
    p2 = ModelProfile("smart_slow", "test", 9, 9, True, True, True, 100000, CostTier.HIGH, LatencyTier.SLOW, False)
    
    selector = ModelSelector([p1, p2])
    
    # 1. Simple plan (low complexity) -> picks cheapest (cheap_fast)
    plan1 = CapabilityPlan(reasoning_model="auto", estimated_complexity="low")
    assert selector.select(plan1).name == "cheap_fast"
    
    # 2. Complex plan -> picks smart_slow
    plan2 = CapabilityPlan(reasoning_model="auto", estimated_complexity="high")
    assert selector.select(plan2).name == "smart_slow"
    
    # 3. Vision required -> picks smart_slow
    plan3 = CapabilityPlan(reasoning_model="auto", required_capabilities=["vision"])
    assert selector.select(plan3).name == "smart_slow"
    
    # 4. Request unknown model -> fallback rules apply
    plan4 = CapabilityPlan(reasoning_model="exact_match")
    assert selector.select(plan4).name == "cheap_fast" # No exact match, falls back to normal scoring


def test_routing_policy_offline():
    policy = RoutingPolicy(offline_mode=True)
    
    plan = CapabilityPlan(
        reasoning_model="auto",
        required_capabilities=["Internet", "memory"],
        required_tools=["browser", "file"],
        requires_internet=True
    )
    
    enforced = policy.enforce(plan)
    assert enforced.requires_internet is False
    assert "Internet" not in enforced.required_capabilities
    assert "browser" not in enforced.required_tools
    
    # Others preserved
    assert "memory" in enforced.required_capabilities
    assert "file" in enforced.required_tools


def test_manager_integration():
    mock_router = MagicMock()
    # Mock LLM generation output
    mock_response = MagicMock()
    mock_response.text = '{"reasoning_model": "auto", "requires_planner": true, "requires_execution": true, "required_tools": ["file"]}'
    mock_router.generate.return_value = mock_response
    
    mock_bus = MagicMock()
    
    profile = ModelProfile("default", "test", 5, 5, False, False, False, 1000, CostTier.FREE, LatencyTier.FAST, True)
    
    manager = CapabilityManager(
        model_router=mock_router,
        event_bus=mock_bus,
        model_profiles=[profile]
    )
    
    manager.register_capability(Capability("file", "File operations", CapabilityType.TOOL))
    
    plan, selected_model = manager.route("Write a file")
    
    assert plan.requires_planner is True
    assert plan.requires_execution is True
    assert "file" in plan.required_tools
    assert selected_model.name == "default"
    
    # Telemetry should be published
    assert mock_bus.publish.called

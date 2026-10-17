"""
Capability Manager — facade for the capability routing subsystem.
"""

import time
from collections.abc import Iterable

from core.capability.models import Capability, CapabilityPlan
from core.capability.policies import RoutingPolicy
from core.capability.profiles import ModelProfile
from core.capability.registry import CapabilityRegistry
from core.capability.router import CapabilityRouter
from core.capability.selector import ModelSelector
from core.capability.telemetry import CapabilityTelemetry
from core.events.bus import EventBus
from core.model_router import ModelRouter


class CapabilityManager:
    """Central orchestrator for capability routing and model selection."""

    def __init__(
        self,
        model_router: ModelRouter,
        event_bus: EventBus,
        model_profiles: Iterable[ModelProfile],
        offline_mode: bool = False
    ) -> None:
        self.registry = CapabilityRegistry()
        self._router = CapabilityRouter(model_router, self.registry)
        self._selector = ModelSelector(model_profiles)
        self._policy = RoutingPolicy(offline_mode=offline_mode)
        self._telemetry = CapabilityTelemetry(event_bus)

    def route(self, user_input: str) -> tuple[CapabilityPlan, ModelProfile]:
        """Determine the required capabilities and select the optimal model.
        
        Args:
            user_input: The raw user request.
            
        Returns:
            A tuple of (CapabilityPlan, ModelProfile).
        """
        start_time = time.time()
        
        # 1. Generate Plan
        raw_plan = self._router.route(user_input)
        
        # 2. Enforce Policies
        plan = self._policy.enforce(raw_plan)
        
        # 3. Select Model
        model_profile = self._selector.select(plan)
        
        # 4. Telemetry
        latency = (time.time() - start_time) * 1000
        self._telemetry.publish_routing_decision(
            user_input=user_input,
            plan=plan,
            selected_model=model_profile.name,
            latency_ms=latency
        )
        
        return plan, model_profile

    def register_capability(self, capability: Capability) -> None:
        """Register a new capability to be considered during routing."""
        self.registry.register(capability)

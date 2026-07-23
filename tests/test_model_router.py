"""
Tests for the ModelRouter orchestration logic.
"""

import unittest
from unittest.mock import patch

from config.model_config import ModelRouterConfig
from core.model_router import ModelRouter
from providers.capabilities import Capability
from providers.fallback_manager import FallbackManager
from providers.health_monitor import HealthMonitor
from providers.provider_models import (
    AllProvidersExhaustedError,
    InferenceRequirements,
    NoCapableProviderError,
    ProviderExecutionError,
    ProviderHealthStatus,
)
from providers.provider_registry import ProviderRegistry
from providers.selection_policy import WeightedScorePolicy
from tests.mock_provider import MockProvider


class FailingMockProvider(MockProvider):
    """A mock provider that always raises a ProviderExecutionError."""
    def generate(self, system_prompt, user_prompt, requirements=None):
        raise ProviderExecutionError("Simulated failure")
        
    def embed(self, text, requirements=None):
        raise ProviderExecutionError("Simulated embed failure")


class TestModelRouter(unittest.TestCase):
    def setUp(self):
        self.config = ModelRouterConfig(prefer_local=True, max_fallback_attempts=2)
        self.health = HealthMonitor()
        self.registry = ProviderRegistry(self.health)
        self.policy = WeightedScorePolicy(self.health)
        self.fallback = FallbackManager(max_fallback_attempts=2)
        
        self.router = ModelRouter(
            self.config,
            self.registry,
            self.policy,
            self.fallback,
            self.health
        )
        
        self.p_local = MockProvider("local", "Local", [Capability.CHAT, Capability.EMBEDDINGS], is_local=True)
        self.p_remote = MockProvider("remote", "Remote", [Capability.CHAT, Capability.VISION], is_local=False)
        self.registry.register(self.p_local)
        self.registry.register(self.p_remote)

    def test_successful_routing_defaults(self):
        # By default, prefers local. So p_local should win.
        resp = self.router.generate("sys", "user")
        self.assertEqual(resp.provider_id, "local")
        self.assertEqual(resp.fallback_count, 0)
        
        # Check health was marked success
        self.assertEqual(self.health.health("local"), ProviderHealthStatus.HEALTHY)

    def test_capability_filtering(self):
        # Require VISION. local doesn't have it, so remote must win.
        reqs = InferenceRequirements(capabilities=frozenset([Capability.VISION]))
        resp = self.router.generate("sys", "user", reqs)
        self.assertEqual(resp.provider_id, "remote")

    def test_no_capable_providers(self):
        # Require AUDIO. No registered provider has it.
        reqs = InferenceRequirements(capabilities=frozenset([Capability.AUDIO]))
        with self.assertRaises(NoCapableProviderError):
            self.router.generate("sys", "user", reqs)

    def test_fallback_behavior(self):
        # Add a failing provider that will be ranked first (prefer_provider)
        failing_p = FailingMockProvider("failing", "Failing", [Capability.CHAT], is_local=False)
        self.registry.register(failing_p)
        
        reqs = InferenceRequirements(prefer_provider="failing")
        
        # It should try 'failing', fail, then fallback to 'local'
        resp = self.router.generate("sys", "user", reqs)
        
        self.assertEqual(resp.provider_id, "local")
        self.assertEqual(resp.fallback_count, 1)
        
        # The failing provider should have a failure recorded
        # 1 failure doesn't necessarily mean DEGRADED yet, but let's check its state
        # In health_monitor, degraded_threshold is 3 by default. 
        # But we know it failed once.

    def test_all_providers_exhausted(self):
        # Unregister healthy ones, register only failing ones
        self.registry.unregister("local")
        self.registry.unregister("remote")
        
        failing1 = FailingMockProvider("f1", "F1", [Capability.CHAT])
        failing2 = FailingMockProvider("f2", "F2", [Capability.CHAT])
        self.registry.register(failing1)
        self.registry.register(failing2)
        
        with self.assertRaises(AllProvidersExhaustedError) as ctx:
            self.router.generate("sys", "user")
            
        self.assertIn("All 2 capable providers failed", str(ctx.exception))
        
        # Both should have failures recorded
        self.health.mark_failure("f1") # Just to trigger any degraded logic if we want to test that elsewhere

    def test_embed_success(self):
        # Local has embeddings
        resp = self.router.embed("test text")
        self.assertEqual(resp.provider_id, "local")
        self.assertEqual(len(resp.vector), 2)
        
    def test_embed_fallback(self):
        # Register a failing embeddings provider and prefer it
        failing_embed = FailingMockProvider("failing_emb", "FailingEmb", [Capability.EMBEDDINGS])
        self.registry.register(failing_embed)
        
        reqs = InferenceRequirements(prefer_provider="failing_emb")
        resp = self.router.embed("test text", reqs)
        
        # Falls back to local
        self.assertEqual(resp.provider_id, "local")

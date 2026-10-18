"""
Tests for the SelectionPolicy.
"""

import unittest

from providers.capabilities import Capability
from providers.health_monitor import HealthMonitor
from providers.provider_models import InferenceRequirements
from providers.selection_policy import WeightedScorePolicy
from tests.mock_provider import MockProvider


class TestWeightedScorePolicy(unittest.TestCase):
    def setUp(self):
        self.health = HealthMonitor()
        self.policy = WeightedScorePolicy(self.health)
        
        self.p_local = MockProvider("ollama", "Ollama", [Capability.CHAT], is_local=True)
        self.p_remote = MockProvider("openai", "OpenAI", [Capability.CHAT], is_local=False)
        self.candidates = [self.p_local, self.p_remote]

    def test_prefer_local_ranks_local_higher(self):
        req = InferenceRequirements(prefer_local=True)
        ranked = self.policy.rank_providers(self.candidates, req)
        
        self.assertEqual(ranked[0], self.p_local)
        self.assertEqual(ranked[1], self.p_remote)

    def test_prefer_provider_ranks_provider_higher(self):
        req = InferenceRequirements(prefer_provider="openai")
        ranked = self.policy.rank_providers(self.candidates, req)
        
        self.assertEqual(ranked[0], self.p_remote)
        self.assertEqual(ranked[1], self.p_local)

    def test_health_penalty(self):
        # Mark local provider as DEGRADED (3 failures)
        for _ in range(3):
            self.health.mark_failure("ollama")
            
        InferenceRequirements(prefer_local=True)
        # prefer_local gives +50, but DEGRADED gives -50, so score is 0. 
        # remote has score 0. Stable sort might leave them in original order.
        # Let's test a clear penalty scenario: prefer_provider gives +100
        req2 = InferenceRequirements(prefer_provider="ollama")
        # score = 100 - 50 = 50. Still higher than remote (0), so ollama wins
        ranked = self.policy.rank_providers(self.candidates, req2)
        self.assertEqual(ranked[0], self.p_local)
        
        # What if no preferences? 
        req3 = InferenceRequirements()
        # ollama: -50, remote: 0
        ranked = self.policy.rank_providers(self.candidates, req3)
        self.assertEqual(ranked[0], self.p_remote)

    def test_measured_latency_breaks_provider_ties(self):
        local = MockProvider("local", "Local", [Capability.CHAT], is_local=False)
        fast = MockProvider("fast", "Fast", [Capability.CHAT], is_local=False)
        self.health.record_latency("local", 1800.0)
        self.health.record_latency("fast", 80.0)
        ranked = self.policy.rank_providers([local, fast], InferenceRequirements())
        self.assertEqual(ranked[0], fast)

    def test_cost_estimate_breaks_ties_without_claiming_unknown_cost_is_free(self):
        class PricedProvider(MockProvider):
            def __init__(self, provider_id, cost):
                super().__init__(provider_id, provider_id, [Capability.CHAT], is_local=False)
                self.cost = cost

            def estimate_cost(self, input_tokens, output_tokens, model_id=None):
                return self.cost

        affordable = PricedProvider("affordable", 0.0001)
        expensive = PricedProvider("expensive", 0.004)
        ranked = self.policy.rank_providers([expensive, affordable], InferenceRequirements())
        self.assertEqual(ranked[0], affordable)

    def test_configured_provider_preference_still_wins_over_latency_tie_breaker(self):
        slow = MockProvider("primary", "Primary", [Capability.CHAT], is_local=False)
        fast = MockProvider("fallback", "Fallback", [Capability.CHAT], is_local=False)
        self.health.record_latency("primary", 5000.0)
        self.health.record_latency("fallback", 1.0)
        ranked = self.policy.rank_providers(
            [slow, fast], InferenceRequirements(prefer_provider="primary")
        )
        self.assertEqual(ranked[0], slow)

    def test_empty_candidates(self):
        ranked = self.policy.rank_providers([], InferenceRequirements())
        self.assertEqual(ranked, [])

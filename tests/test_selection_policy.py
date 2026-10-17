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

    def test_empty_candidates(self):
        ranked = self.policy.rank_providers([], InferenceRequirements())
        self.assertEqual(ranked, [])

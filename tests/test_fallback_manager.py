"""
Tests for the FallbackManager.
"""

import unittest

from providers.capabilities import Capability
from providers.fallback_manager import FallbackManager
from providers.provider_models import AllProvidersExhaustedError
from tests.mock_provider import MockProvider


class TestFallbackManager(unittest.TestCase):
    def setUp(self):
        self.manager = FallbackManager(max_fallback_attempts=2)
        self.p1 = MockProvider("p1", "P1", [Capability.CHAT])
        self.p2 = MockProvider("p2", "P2", [Capability.CHAT])
        self.p3 = MockProvider("p3", "P3", [Capability.CHAT])
        self.p4 = MockProvider("p4", "P4", [Capability.CHAT])
        
        self.candidates = [self.p1, self.p2, self.p3, self.p4]

    def test_get_next_yields_in_order(self):
        chain = self.manager.create_chain(self.candidates)
        
        self.assertEqual(chain.get_next(), self.p1)
        self.assertEqual(chain.fallback_count, 0)
        
        self.assertEqual(chain.get_next(), self.p2)
        self.assertEqual(chain.fallback_count, 1)

    def test_respects_max_fallbacks(self):
        chain = self.manager.create_chain(self.candidates)
        
        # Max attempts = 2 + 1 initial = 3 total
        chain.get_next()  # Initial (p1)
        chain.get_next()  # Fallback 1 (p2)
        chain.get_next()  # Fallback 2 (p3)
        
        with self.assertRaises(AllProvidersExhaustedError):
            chain.get_next()  # Exceeds max fallbacks

    def test_exhausts_candidates(self):
        short_candidates = [self.p1]
        chain = self.manager.create_chain(short_candidates)
        
        chain.get_next()  # Initial (p1)
        
        with self.assertRaises(AllProvidersExhaustedError):
            chain.get_next()  # No more candidates

    def test_does_not_repeat_providers(self):
        # Even if candidates list has duplicates, it should skip them
        duplicates = [self.p1, self.p1, self.p2]
        chain = self.manager.create_chain(duplicates)
        
        self.assertEqual(chain.get_next(), self.p1)
        self.assertEqual(chain.get_next(), self.p2)

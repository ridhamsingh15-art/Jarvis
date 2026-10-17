"""
Tests for the ProviderRegistry.
"""

import unittest

from providers.capabilities import Capability
from providers.health_monitor import HealthMonitor
from providers.provider_registry import ProviderRegistry
from tests.mock_provider import MockProvider


class TestProviderRegistry(unittest.TestCase):
    def setUp(self):
        self.health = HealthMonitor()
        self.registry = ProviderRegistry(self.health)
        self.p1 = MockProvider("p1", "Provider 1", [Capability.CHAT])
        self.p2 = MockProvider("p2", "Provider 2", [Capability.CHAT, Capability.VISION])

    def test_register_and_get(self):
        self.registry.register(self.p1)
        self.assertEqual(self.registry.get_provider("p1"), self.p1)
        self.assertIsNone(self.registry.get_provider("nonexistent"))

    def test_duplicate_registration_raises(self):
        self.registry.register(self.p1)
        with self.assertRaises(ValueError):
            self.registry.register(self.p1)

    def test_invalid_registration_raises(self):
        with self.assertRaises(TypeError):
            self.registry.register("not a provider")  # type: ignore

    def test_unregister(self):
        self.registry.register(self.p1)
        self.registry.unregister("p1")
        self.assertIsNone(self.registry.get_provider("p1"))
        
        # Unregistering non-existent should not raise
        self.registry.unregister("p1")

    def test_list_providers(self):
        self.registry.register(self.p1)
        self.registry.register(self.p2)
        providers = self.registry.list_providers()
        self.assertEqual(len(providers), 2)
        self.assertIn(self.p1, providers)
        self.assertIn(self.p2, providers)

    def test_list_by_capability(self):
        self.registry.register(self.p1)
        self.registry.register(self.p2)
        
        chat_providers = self.registry.list_by_capability(Capability.CHAT)
        self.assertEqual(len(chat_providers), 2)
        
        vision_providers = self.registry.list_by_capability(Capability.VISION)
        self.assertEqual(len(vision_providers), 1)
        self.assertEqual(vision_providers[0], self.p2)

    def test_list_healthy_providers(self):
        self.registry.register(self.p1)
        self.registry.register(self.p2)
        
        # Initially both healthy
        healthy = self.registry.list_healthy_providers()
        self.assertEqual(len(healthy), 2)
        
        # Mark p1 as UNAVAILABLE (requires 8 failures by default)
        for _ in range(8):
            self.health.mark_failure("p1")
            
        healthy_now = self.registry.list_healthy_providers()
        self.assertEqual(len(healthy_now), 1)
        self.assertEqual(healthy_now[0], self.p2)

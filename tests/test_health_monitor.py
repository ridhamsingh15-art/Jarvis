"""
Tests for the HealthMonitor.
"""

import unittest

from providers.health_monitor import HealthMonitor
from providers.provider_models import ProviderHealthStatus


class TestHealthMonitor(unittest.TestCase):
    def setUp(self):
        self.health = HealthMonitor(
            degraded_threshold=3,
            unavailable_threshold=5,
            recovery_required_successes=2
        )

    def test_initial_state_is_healthy(self):
        self.assertEqual(self.health.health("p1"), ProviderHealthStatus.HEALTHY)

    def test_degraded_threshold(self):
        self.health.mark_failure("p1")
        self.health.mark_failure("p1")
        self.assertEqual(self.health.health("p1"), ProviderHealthStatus.HEALTHY)
        
        self.health.mark_failure("p1")  # 3rd failure
        self.assertEqual(self.health.health("p1"), ProviderHealthStatus.DEGRADED)

    def test_unavailable_threshold(self):
        for _ in range(5):
            self.health.mark_failure("p1")
            
        self.assertEqual(self.health.health("p1"), ProviderHealthStatus.UNAVAILABLE)

    def test_success_resets_consecutive_failures(self):
        self.health.mark_failure("p1")
        self.health.mark_failure("p1")
        self.health.mark_success("p1")
        self.health.mark_failure("p1")
        
        # Total consecutive failures is 1 now, so should be HEALTHY
        self.assertEqual(self.health.health("p1"), ProviderHealthStatus.HEALTHY)

    def test_recovery_from_degraded(self):
        for _ in range(3):
            self.health.mark_failure("p1")
        self.assertEqual(self.health.health("p1"), ProviderHealthStatus.DEGRADED)
        
        self.health.mark_success("p1")  # 1st success
        self.assertEqual(self.health.health("p1"), ProviderHealthStatus.DEGRADED)
        
        self.health.mark_success("p1")  # 2nd success
        self.assertEqual(self.health.health("p1"), ProviderHealthStatus.HEALTHY)

    def test_recovery_from_unavailable(self):
        for _ in range(5):
            self.health.mark_failure("p1")
        self.assertEqual(self.health.health("p1"), ProviderHealthStatus.UNAVAILABLE)
        
        self.health.mark_success("p1")
        self.health.mark_success("p1")
        self.assertEqual(self.health.health("p1"), ProviderHealthStatus.HEALTHY)

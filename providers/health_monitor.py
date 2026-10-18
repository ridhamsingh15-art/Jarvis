"""
Health monitoring for AI providers.

Tracks operational state based on success/failure signals.
Does not perform background polling; state is updated passively
by the fallback manager or actively by external health checks.
"""

import logging
import threading

from providers.provider_models import ProviderHealthStatus

logger = logging.getLogger(__name__)


class HealthMonitor:
    """Tracks health state of providers using a circuit-breaker pattern."""

    def __init__(
        self,
        degraded_threshold: int = 3,
        unavailable_threshold: int = 8,
        recovery_required_successes: int = 2,
    ) -> None:
        """Initialize the health monitor.
        
        Args:
            degraded_threshold: Consecutive failures before DEGRADED.
            unavailable_threshold: Total failures before UNAVAILABLE.
            recovery_required_successes: Consecutive successes to recover.
        """
        self._degraded_threshold = degraded_threshold
        self._unavailable_threshold = unavailable_threshold
        self._recovery_required_successes = recovery_required_successes

        self._lock = threading.RLock()
        self._states: dict[str, ProviderHealthStatus] = {}
        self._consecutive_failures: dict[str, int] = {}
        self._total_failures: dict[str, int] = {}  # for unavailable threshold
        self._consecutive_successes: dict[str, int] = {}
        self._latency_ewma_ms: dict[str, float] = {}

    def mark_success(self, provider_id: str) -> None:
        """Record a successful operation for a provider."""
        with self._lock:
            # Initialize if not present
            if provider_id not in self._states:
                self._initialize_provider(provider_id)
                
            state = self._states[provider_id]
            
            # Reset failure counters
            self._consecutive_failures[provider_id] = 0
            
            # Increment successes if recovering
            if state != ProviderHealthStatus.HEALTHY:
                self._consecutive_successes[provider_id] += 1
                if self._consecutive_successes[provider_id] >= self._recovery_required_successes:
                    self._states[provider_id] = ProviderHealthStatus.HEALTHY
                    self._total_failures[provider_id] = 0  # Full reset on recovery
                    logger.info("Provider %s: %s -> HEALTHY (recovered)", provider_id, state.name)
            else:
                self._consecutive_successes[provider_id] = 1

    def mark_failure(self, provider_id: str) -> None:
        """Record a failed operation for a provider."""
        with self._lock:
            if provider_id not in self._states:
                self._initialize_provider(provider_id)
                
            self._consecutive_successes[provider_id] = 0
            self._consecutive_failures[provider_id] += 1
            self._total_failures[provider_id] += 1
            
            state = self._states[provider_id]
            
            if state == ProviderHealthStatus.HEALTHY and self._consecutive_failures[provider_id] >= self._degraded_threshold:
                self._states[provider_id] = ProviderHealthStatus.DEGRADED
                logger.warning("Provider %s: HEALTHY -> DEGRADED (%d failures)", provider_id, self._consecutive_failures[provider_id])
                
            elif state != ProviderHealthStatus.UNAVAILABLE and self._total_failures[provider_id] >= self._unavailable_threshold:
                self._states[provider_id] = ProviderHealthStatus.UNAVAILABLE
                logger.error("Provider %s: %s -> UNAVAILABLE (%d total failures)", provider_id, state.name, self._total_failures[provider_id])

    def record_latency(self, provider_id: str, latency_ms: float) -> None:
        """Track smoothed successful latency for routing decisions."""
        if isinstance(latency_ms, bool) or not isinstance(latency_ms, (int, float)) or latency_ms < 0:
            return
        with self._lock:
            previous = self._latency_ewma_ms.get(provider_id)
            self._latency_ewma_ms[provider_id] = (
                float(latency_ms) if previous is None
                else (0.25 * float(latency_ms)) + (0.75 * previous)
            )

    def average_latency_ms(self, provider_id: str) -> float | None:
        """Return the smoothed latency, or None before a successful observation."""
        with self._lock:
            return self._latency_ewma_ms.get(provider_id)

    def health(self, provider_id: str) -> ProviderHealthStatus:
        """Get the current health status of a provider."""
        with self._lock:
            return self._states.get(provider_id, ProviderHealthStatus.HEALTHY)

    def _initialize_provider(self, provider_id: str) -> None:
        """Setup initial tracking state for a new provider."""
        self._states[provider_id] = ProviderHealthStatus.HEALTHY
        self._consecutive_failures[provider_id] = 0
        self._total_failures[provider_id] = 0
        self._consecutive_successes[provider_id] = 0

"""
Routing policies for selecting the best provider.
"""

from abc import ABC, abstractmethod

from providers.base_provider import BaseProvider
from providers.health_monitor import HealthMonitor
from providers.provider_models import InferenceRequirements, ProviderHealthStatus


class SelectionPolicy(ABC):
    """Strategy interface for ranking candidate providers."""

    @abstractmethod
    def rank_providers(
        self,
        candidates: list[BaseProvider],
        requirements: InferenceRequirements,
    ) -> list[BaseProvider]:
        """Rank candidates from best to worst.
        
        Args:
            candidates: List of capable providers.
            requirements: Routing constraints and hints.
            
        Returns:
            A new list of candidates ordered by preference.
        """


class WeightedScorePolicy(SelectionPolicy):
    """A policy that scores providers based on weighted dimensions."""

    def __init__(self, health_monitor: HealthMonitor) -> None:
        """Initialize the policy.
        
        Args:
            health_monitor: Monitor to penalize degraded providers.
        """
        self._health_monitor = health_monitor

    def rank_providers(
        self,
        candidates: list[BaseProvider],
        requirements: InferenceRequirements,
    ) -> list[BaseProvider]:
        """Rank providers using a simple weighted scoring algorithm."""
        if not candidates:
            return []

        def score_provider(provider: BaseProvider) -> float:
            score = 0.0

            # 1. Soft Preference
            if requirements.prefer_provider and provider.provider_id == requirements.prefer_provider:
                score += 100.0

            # 2. Locality (Privacy)
            if requirements.prefer_local and provider.is_local:
                score += 50.0

            # 3. Health status penalty
            health_status = self._health_monitor.health(provider.provider_id)
            if health_status == ProviderHealthStatus.DEGRADED:
                score -= 50.0

            # Note: Task complexity and historical latency would be factored
            # in here for a more advanced production implementation.

            return score

        # Sort descending by score. Stable sort preserves original registry order as tiebreaker.
        return sorted(candidates, key=score_provider, reverse=True)

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
        """Rank providers by configuration preference, privacy, health, latency and cost.

        Cost/latency scores are tie-breakers for provider selection—not promises.
        Monetary comparison uses a representative 1,024-input/256-output request;
        explicit max-cost and max-latency requirements are filtered by ModelRouter
        before this ranking step.
        """
        if not candidates:
            return []

        def score_provider(provider: BaseProvider) -> float:
            score = 0.0

            # Configuration and request preferences are intentionally strongest:
            # selecting a primary provider is explicit unless it fails.
            if requirements.prefer_provider and provider.provider_id == requirements.prefer_provider:
                score += 100.0

            resolved_model = provider.resolve_model_id(requirements)
            if requirements.prefer_model and resolved_model == requirements.prefer_model:
                score += 25.0

            # Privacy/locality preference.
            if requirements.prefer_local and provider.is_local:
                score += 50.0

            # Degraded providers remain usable as fallback candidates, but rank lower.
            if self._health_monitor.health(provider.provider_id) == ProviderHealthStatus.DEGRADED:
                score -= 50.0

            # A measured latency estimate makes healthy alternatives rankable. Unknown
            # latency receives a small neutral score instead of an invented measurement.
            latency = self._health_monitor.average_latency_ms(provider.provider_id)
            if latency is not None:
                score += max(0.0, 20.0 - min(20.0, float(latency) / 250.0))

            # Use a transparent reference request for cost ranking. Unknown prices
            # contribute no score; a cost ceiling is enforced separately and never
            # treats unknown vendor pricing as free.
            try:
                model_id = provider.resolve_model_id(requirements)
                estimated_cost = provider.estimate_cost(1024, 256, model_id)
            except Exception:  # noqa: BLE001 - a scoring failure must not prevent fallback routing.
                estimated_cost = None
            if estimated_cost is not None and estimated_cost >= 0:
                score += max(0.0, 10.0 - min(10.0, float(estimated_cost) * 2000.0))

            return score

        # Stable sort preserves registry order when scores are equal.
        return sorted(candidates, key=score_provider, reverse=True)

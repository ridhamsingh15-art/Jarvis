"""
Fallback management for routing requests.
"""

from typing import List, Optional, Set

from providers.base_provider import BaseProvider
from providers.provider_models import AllProvidersExhaustedError


class FallbackChain:
    """Stateful iterator for a single request's fallback chain."""

    def __init__(self, candidates: List[BaseProvider], max_fallback_attempts: int) -> None:
        """Initialize the chain.
        
        Args:
            candidates: Ordered list of providers to try.
            max_fallback_attempts: Maximum number of fallbacks (0 = first try only).
        """
        self._candidates = candidates
        self._max_attempts = max_fallback_attempts + 1  # 1 initial + N fallbacks
        self._attempts = 0
        self._tried_provider_ids: Set[str] = set()

    def get_next(self) -> BaseProvider:
        """Get the next candidate provider.
        
        Returns:
            The next BaseProvider to try.
            
        Raises:
            AllProvidersExhaustedError: If max attempts reached or no candidates left.
        """
        if self._attempts >= self._max_attempts:
            raise AllProvidersExhaustedError("Maximum fallback attempts exceeded.")

        for provider in self._candidates:
            if provider.provider_id not in self._tried_provider_ids:
                self._tried_provider_ids.add(provider.provider_id)
                self._attempts += 1
                return provider

        raise AllProvidersExhaustedError("All capable candidate providers have been exhausted.")

    @property
    def fallback_count(self) -> int:
        """Number of fallbacks that have occurred (0 if on first attempt)."""
        return max(0, self._attempts - 1)


class FallbackManager:
    """Factory for creating FallbackChains."""

    def __init__(self, max_fallback_attempts: int = 3) -> None:
        """Initialize the manager.
        
        Args:
            max_fallback_attempts: Default max fallbacks allowed per request.
        """
        self._max_fallback_attempts = max_fallback_attempts

    def create_chain(self, candidates: List[BaseProvider]) -> FallbackChain:
        """Create a new fallback chain for a request.
        
        Args:
            candidates: Ranked list of candidate providers.
            
        Returns:
            A new FallbackChain instance.
        """
        return FallbackChain(candidates, self._max_fallback_attempts)

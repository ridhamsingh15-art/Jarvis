"""
Data models and exceptions for the Provider Infrastructure.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto

from core.exceptions import JarvisError
from providers.capabilities import Capability


class ProviderHealthStatus(Enum):
    """Health states for an AI provider."""
    HEALTHY = auto()
    DEGRADED = auto()
    UNAVAILABLE = auto()


@dataclass(frozen=True)
class ProviderMetadata:
    """Metadata describing a provider."""
    provider_id: str
    display_name: str
    capabilities: frozenset[Capability]
    is_local: bool


@dataclass(frozen=True)
class InferenceRequirements:
    """Routing hints and constraints for a request."""
    capabilities: frozenset[Capability] = field(default_factory=frozenset)
    max_latency_ms: int | None = None
    max_cost_per_request: float | None = None
    min_context_length: int | None = None
    prefer_local: bool = False
    prefer_provider: str | None = None
    task_complexity: str = "MODERATE"
    prefer_model: str | None = None
    role: str | None = None
    max_output_tokens: int | None = None

    def __post_init__(self) -> None:
        """Reject invalid hard bounds before they reach provider APIs."""
        if self.max_latency_ms is not None and (
            isinstance(self.max_latency_ms, bool)
            or not isinstance(self.max_latency_ms, int)
            or self.max_latency_ms < 0
        ):
            raise ValueError("max_latency_ms must be a non-negative integer or None")
        if self.max_cost_per_request is not None and (
            isinstance(self.max_cost_per_request, bool)
            or self.max_cost_per_request < 0
        ):
            raise ValueError("max_cost_per_request must be non-negative or None")
        if self.min_context_length is not None and (
            isinstance(self.min_context_length, bool)
            or not isinstance(self.min_context_length, int)
            or self.min_context_length <= 0
        ):
            raise ValueError("min_context_length must be a positive integer or None")
        if self.max_output_tokens is not None and (
            isinstance(self.max_output_tokens, bool)
            or not isinstance(self.max_output_tokens, int)
            or self.max_output_tokens <= 0
        ):
            raise ValueError("max_output_tokens must be a positive integer or None")


@dataclass(frozen=True)
class TokenUsage:
    """Token consumption for a request."""
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


@dataclass(frozen=True)
class ModelResponse:
    """Response envelope for text generation."""
    text: str
    provider_id: str
    model_id: str
    latency_ms: int
    fallback_count: int = 0
    token_usage: TokenUsage = field(default_factory=TokenUsage)
    cost: float | None = None


@dataclass(frozen=True)
class EmbeddingResponse:
    """Response envelope for vector embeddings."""
    vector: list[float]
    dimensions: int
    provider_id: str
    model_id: str
    latency_ms: int


# --- Exceptions ---

class RouterError(JarvisError):
    """Base exception for all Model Router errors."""


class NoCapableProviderError(RouterError):
    """Raised when no provider in the registry supports the required capabilities."""


class AllProvidersExhaustedError(RouterError):
    """Raised when all candidate providers have been tried and failed."""


class ProviderExecutionError(RouterError):
    """Raised by a provider when generation fails."""

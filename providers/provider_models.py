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

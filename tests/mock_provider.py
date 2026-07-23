"""
Shared mock provider for unit tests.
"""

from typing import Optional

from providers.base_provider import BaseProvider
from providers.capabilities import Capability
from providers.provider_models import (
    EmbeddingResponse,
    InferenceRequirements,
    ModelResponse,
    ProviderHealthStatus,
)


class MockProvider(BaseProvider):
    """A mock provider for testing routing logic."""

    def __init__(
        self,
        provider_id: str,
        display_name: str,
        capabilities: list[Capability],
        is_local: bool = False,
    ) -> None:
        self._id = provider_id
        self._name = display_name
        self._caps = frozenset(capabilities)
        self._local = is_local

    @property
    def provider_id(self) -> str:
        return self._id

    @property
    def display_name(self) -> str:
        return self._name

    @property
    def capabilities(self) -> frozenset[Capability]:
        return self._caps

    @property
    def is_local(self) -> bool:
        return self._local

    def initialize(self) -> None:
        pass

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        requirements: Optional[InferenceRequirements] = None,
    ) -> ModelResponse:
        return ModelResponse(
            text="mock response",
            provider_id=self._id,
            model_id="mock-model",
            latency_ms=10,
        )

    def embed(
        self, text: str, requirements: Optional[InferenceRequirements] = None
    ) -> EmbeddingResponse:
        return EmbeddingResponse(
            vector=[0.1, 0.2],
            dimensions=2,
            provider_id=self._id,
            model_id="mock-model",
            latency_ms=10,
        )

    def health_check(self) -> ProviderHealthStatus:
        return ProviderHealthStatus.HEALTHY

    def shutdown(self) -> None:
        pass

    def estimate_cost(
        self, input_tokens: int, output_tokens: int, model_id: Optional[str] = None
    ) -> float:
        return 0.0

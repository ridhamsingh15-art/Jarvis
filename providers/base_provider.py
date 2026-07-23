"""
Abstract base class for all AI providers.
"""

from abc import ABC, abstractmethod

from providers.capabilities import Capability
from providers.provider_models import (
    EmbeddingResponse,
    InferenceRequirements,
    ModelResponse,
    ProviderHealthStatus,
)


class BaseProvider(ABC):
    """Abstract base interface for all AI model providers.
    
    A provider is responsible for translating the Jarvis generic pipeline
    requests into provider-specific API calls.
    """

    @property
    @abstractmethod
    def provider_id(self) -> str:
        """Globally unique identifier for this provider (e.g. 'openai')."""

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Human-readable name (e.g. 'OpenAI')."""

    @property
    @abstractmethod
    def capabilities(self) -> frozenset[Capability]:
        """Set of capabilities this provider supports."""

    @property
    @abstractmethod
    def is_local(self) -> bool:
        """True if the provider runs on the local machine (e.g., Ollama)."""

    @abstractmethod
    def initialize(self) -> None:
        """One-time setup (e.g., loading SDK, validating keys)."""

    @abstractmethod
    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        requirements: InferenceRequirements | None = None,
    ) -> ModelResponse:
        """Execute text generation.
        
        Args:
            system_prompt: The system instruction context.
            user_prompt: The user's input.
            requirements: Optional routing hints/constraints.
            
        Returns:
            ModelResponse containing the output text and metadata.
            
        Raises:
            ProviderExecutionError: If the provider fails to generate a response.
        """

    @abstractmethod
    def embed(
        self,
        text: str,
        requirements: InferenceRequirements | None = None,
    ) -> EmbeddingResponse:
        """Generate vector embeddings for the given text.
        
        Args:
            text: Text to embed.
            requirements: Optional routing hints.
            
        Returns:
            EmbeddingResponse containing the vector and metadata.
            
        Raises:
            ProviderExecutionError: If embedding generation fails.
        """

    @abstractmethod
    def health_check(self) -> ProviderHealthStatus:
        """Check the operational health of the provider."""

    @abstractmethod
    def shutdown(self) -> None:
        """Graceful cleanup of resources."""

    def supports(self, capability: Capability) -> bool:
        """Check if this provider supports a specific capability.
        
        Args:
            capability: The capability to check.
            
        Returns:
            True if supported, False otherwise.
        """
        return capability in self.capabilities

    @abstractmethod
    def estimate_cost(
        self,
        input_tokens: int,
        output_tokens: int,
        model_id: str | None = None,
    ) -> float:
        """Estimate the cost of a request in USD.
        
        Args:
            input_tokens: Estimated number of input tokens.
            output_tokens: Estimated number of output tokens.
            model_id: Specific model ID to use for pricing, or None for default.
            
        Returns:
            Estimated cost in USD (0.0 for local models).
        """

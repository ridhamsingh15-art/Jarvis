"""
Public interface for the Model Router subsystem.
"""

from abc import ABC, abstractmethod
from typing import Optional

from providers.provider_models import (
    EmbeddingResponse,
    InferenceRequirements,
    ModelResponse,
)


class ModelGateway(ABC):
    """Facade for AI inference.
    
    This is the only interface the rest of the Jarvis pipeline (e.g., Planner)
    should interact with. It delegates all underlying logic to the ModelRouter,
    shielding the caller from provider selection, failover mechanics, and state.
    """

    @abstractmethod
    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        requirements: Optional[InferenceRequirements] = None,
    ) -> ModelResponse:
        """Generate text from an optimal AI provider.
        
        Args:
            system_prompt: The system instruction context.
            user_prompt: The user's specific request.
            requirements: Optional routing hints and constraints. If omitted,
                          default routing logic is applied.
                          
        Returns:
            ModelResponse containing the raw text and metadata about the routing.
            
        Raises:
            NoCapableProviderError: If no registered provider meets the requirements.
            AllProvidersExhaustedError: If all candidate providers fail during execution.
            RouterError: For generic subsystem failures.
        """

    @abstractmethod
    def embed(
        self,
        text: str,
        requirements: Optional[InferenceRequirements] = None,
    ) -> EmbeddingResponse:
        """Generate a vector embedding for the given text.
        
        Args:
            text: The string to embed.
            requirements: Optional routing hints. The capability Capability.EMBEDDINGS
                          is automatically inferred by the router.
                          
        Returns:
            EmbeddingResponse containing the vector array and metadata.
            
        Raises:
            NoCapableProviderError: If no registered provider supports embeddings.
            AllProvidersExhaustedError: If all capable providers fail.
            RouterError: For generic subsystem failures.
        """

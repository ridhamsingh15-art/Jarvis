"""
Ollama local provider implementation.
"""

import logging
import time
from typing import Any, Dict, Optional
import requests

from providers.base_provider import BaseProvider
from providers.capabilities import Capability
from providers.provider_models import (
    EmbeddingResponse,
    InferenceRequirements,
    ModelResponse,
    ProviderHealthStatus,
    TokenUsage,
)
from providers.provider_exceptions import (
    ProviderAPIError,
    ProviderConnectionError,
    ProviderTimeoutError,
)
from config.providers import PROVIDER_CONFIG

logger = logging.getLogger(__name__)


class OllamaProvider(BaseProvider):
    """Ollama local AI provider implementation."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self._config = config or PROVIDER_CONFIG.get("ollama", {})
        self._base_url = self._config.get("base_url", "http://localhost:11434")
        self._default_model = self._config.get("default_model", "llama3")
        self._default_embed_model = self._config.get("default_embedding_model", "nomic-embed-text")
        self._timeout = self._config.get("timeout_seconds", 30)

    @property
    def provider_id(self) -> str:
        return "ollama"

    @property
    def display_name(self) -> str:
        return "Ollama (Local)"

    @property
    def capabilities(self) -> frozenset[Capability]:
        return frozenset([
            Capability.CHAT,
            Capability.EMBEDDINGS,
        ])

    @property
    def is_local(self) -> bool:
        return True

    def initialize(self) -> None:
        logger.info("Initializing %s provider at %s", self.display_name, self._base_url)

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        requirements: Optional[InferenceRequirements] = None,
    ) -> ModelResponse:
        model_id = self._default_model
        if requirements and requirements.prefer_provider == self.provider_id:
            pass
            
        start_time = time.time()
        
        url = f"{self._base_url}/api/generate"
        payload = {
            "model": model_id,
            "system": system_prompt,
            "prompt": user_prompt,
            "stream": False
        }
        
        try:
            logger.debug("Sending generation request to Ollama: %s", model_id)
            response = requests.post(url, json=payload, timeout=self._timeout)
            response.raise_for_status()
            data = response.json()
            
            latency_ms = int((time.time() - start_time) * 1000)
            
            input_tokens = data.get("prompt_eval_count", 0)
            output_tokens = data.get("eval_count", 0)
            token_usage = TokenUsage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=input_tokens + output_tokens
            )
            
            return ModelResponse(
                text=data.get("response", ""),
                provider_id=self.provider_id,
                model_id=model_id,
                latency_ms=latency_ms,
                token_usage=token_usage,
                cost=0.0
            )
            
        except requests.exceptions.Timeout as e:
            logger.error("Ollama request timed out: %s", e)
            raise ProviderTimeoutError(f"Ollama request timed out: {e}") from e
        except requests.exceptions.ConnectionError as e:
            logger.error("Failed to connect to Ollama: %s", e)
            raise ProviderConnectionError(f"Failed to connect to Ollama at {self._base_url}") from e
        except requests.exceptions.RequestException as e:
            logger.error("Ollama API error: %s", e)
            raise ProviderAPIError(f"Ollama API error: {e}") from e

    def embed(
        self,
        text: str,
        requirements: Optional[InferenceRequirements] = None,
    ) -> EmbeddingResponse:
        model_id = self._default_embed_model
        start_time = time.time()
        
        url = f"{self._base_url}/api/embeddings"
        payload = {
            "model": model_id,
            "prompt": text
        }
        
        try:
            logger.debug("Sending embedding request to Ollama: %s", model_id)
            response = requests.post(url, json=payload, timeout=self._timeout)
            response.raise_for_status()
            data = response.json()
            
            latency_ms = int((time.time() - start_time) * 1000)
            vector = data.get("embedding", [])
            
            return EmbeddingResponse(
                vector=vector,
                dimensions=len(vector),
                provider_id=self.provider_id,
                model_id=model_id,
                latency_ms=latency_ms
            )
            
        except requests.exceptions.Timeout as e:
            logger.error("Ollama embedding request timed out: %s", e)
            raise ProviderTimeoutError(f"Ollama request timed out: {e}") from e
        except requests.exceptions.ConnectionError as e:
            logger.error("Failed to connect to Ollama: %s", e)
            raise ProviderConnectionError(f"Failed to connect to Ollama at {self._base_url}") from e
        except requests.exceptions.RequestException as e:
            logger.error("Ollama API error: %s", e)
            raise ProviderAPIError(f"Ollama API error: {e}") from e

    def health_check(self) -> ProviderHealthStatus:
        url = f"{self._base_url}/api/tags"
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                return ProviderHealthStatus.HEALTHY
            return ProviderHealthStatus.DEGRADED
        except Exception as e:
            logger.warning("Ollama health check failed: %s", e)
            return ProviderHealthStatus.UNAVAILABLE

    def shutdown(self) -> None:
        logger.info("Shutting down %s provider", self.display_name)

    def estimate_cost(
        self,
        input_tokens: int,
        output_tokens: int,
        model_id: Optional[str] = None,
    ) -> float:
        return 0.0

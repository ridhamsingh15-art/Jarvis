"""
Google Gemini provider implementation via REST API.
"""

import logging
import os
import time
from typing import Any

import requests

from config.providers import PROVIDER_CONFIG
from providers.base_provider import BaseProvider
from providers.capabilities import Capability
from providers.provider_exceptions import (
    ProviderAPIError,
    ProviderAuthenticationError,
    ProviderConfigurationError,
    ProviderConnectionError,
    ProviderTimeoutError,
)
from providers.provider_models import (
    EmbeddingResponse,
    InferenceRequirements,
    ModelResponse,
    ProviderHealthStatus,
    TokenUsage,
)

logger = logging.getLogger(__name__)


class GeminiProvider(BaseProvider):
    """Google Gemini AI provider implementation."""

    def __init__(self, config: dict[str, Any] | None = None):
        self._config = config or PROVIDER_CONFIG.get("gemini", {})
        self._api_key = self._config.get("api_key") or os.environ.get("GEMINI_API_KEY")
        self._default_model = self._config.get("default_model", "gemini-3.8-flash")
        self._models = dict(self._config.get("models", {}))
        self._models.setdefault("general", self._default_model)
        self._default_embed_model = self._config.get("default_embedding_model", "gemini-embedding-2")
        self._timeout = self._config.get("timeout_seconds", 30)
        self._base_url = "https://generativelanguage.googleapis.com/v1beta/models"
        self._is_initialized = False

    @property
    def provider_id(self) -> str:
        return "gemini"

    @property
    def display_name(self) -> str:
        return "Google Gemini"

    @property
    def capabilities(self) -> frozenset[Capability]:
        return frozenset([
            Capability.CHAT,
            Capability.CODING,
            Capability.REASONING,
            Capability.EMBEDDINGS,
            Capability.TOOL_USE,
        ])

    @property
    def is_local(self) -> bool:
        return False

    def initialize(self) -> None:
        logger.info("Initializing %s provider", self.display_name)
        if not self._api_key:
            raise ProviderConfigurationError("Gemini API key not found in config or environment")
        self._is_initialized = True

    def _resolve_model(self, requirements: InferenceRequirements | None) -> str:
        """Select a configured provider-native model for the requested role."""
        if requirements and requirements.prefer_model:
            return requirements.prefer_model
        if requirements and requirements.role:
            model = self._models.get(str(requirements.role).lower())
            if model:
                return model
        if requirements:
            if Capability.CODING in requirements.capabilities or Capability.REASONING in requirements.capabilities:
                return self._models.get("reasoning" if Capability.REASONING in requirements.capabilities else "coding", self._default_model)
            if Capability.VISION in requirements.capabilities:
                return self._models.get("vision", self._default_model)
            if requirements.task_complexity in {"SIMPLE", 1, 2, 3}:
                return self._models.get("fast", self._default_model)
        return self._models.get("general", self._default_model)

    def context_window_tokens(
        self, requirements: InferenceRequirements | None = None
    ) -> int | None:
        model = self._resolve_model(requirements)
        if model == "gemini-4-argon":
            return 1_048_576
        return None

    def resolve_model_id(self, requirements: InferenceRequirements | None = None) -> str:
        """Return the actual configured model tag this request would use."""
        return self._resolve_model(requirements)

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        requirements: InferenceRequirements | None = None,
    ) -> ModelResponse:
        if not self._is_initialized:
            self.initialize()
            
        model_id = self._resolve_model(requirements)
            
        start_time = time.time()
        url = f"{self._base_url}/{model_id}:generateContent"
        
        payload = {
            "contents": [
                {"role": "user", "parts": [{"text": user_prompt}]}
            ],
            "systemInstruction": {
                "parts": [{"text": system_prompt}]
            }
        }
        if requirements and requirements.max_output_tokens is not None:
            payload["generationConfig"] = {
                "maxOutputTokens": requirements.max_output_tokens
            }
        
        try:
            logger.debug("Sending generation request to Gemini: %s", model_id)
            response = requests.post(url, json=payload, timeout=self._timeout, headers={"x-goog-api-key": self._api_key})
            
            if response.status_code in (401, 403):
                raise ProviderAuthenticationError("Invalid API key or unauthorized access")
                
            response.raise_for_status()
            data = response.json()
            
            latency_ms = int((time.time() - start_time) * 1000)
            
            candidates = data.get("candidates", [])
            text = ""
            if candidates:
                content = candidates[0].get("content", {})
                parts = content.get("parts", [])
                if parts:
                    text = parts[0].get("text", "")
            
            usage_meta = data.get("usageMetadata", {})
            input_tokens = usage_meta.get("promptTokenCount", 0)
            output_tokens = usage_meta.get("candidatesTokenCount", 0)
            token_usage = TokenUsage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=usage_meta.get("totalTokenCount", 0)
            )
            
            cost = self.estimate_cost(input_tokens, output_tokens, model_id)
            
            return ModelResponse(
                text=text,
                provider_id=self.provider_id,
                model_id=model_id,
                latency_ms=latency_ms,
                token_usage=token_usage,
                cost=cost
            )
            
        except requests.exceptions.Timeout as e:
            logger.error("Gemini request timed out: %s", e)
            raise ProviderTimeoutError(f"Gemini request timed out: {e}") from e
        except requests.exceptions.ConnectionError as e:
            logger.error("Failed to connect to Gemini: %s", e)
            raise ProviderConnectionError(f"Failed to connect to Gemini API: {e}") from e
        except requests.exceptions.RequestException as e:
            logger.error("Gemini API error: %s", e)
            raise ProviderAPIError(f"Gemini API error: {e}") from e

    def embed(
        self,
        text: str,
        requirements: InferenceRequirements | None = None,
    ) -> EmbeddingResponse:
        if not self._is_initialized:
            self.initialize()
            
        model_id = self._default_embed_model
        start_time = time.time()
        
        url = f"{self._base_url}/{model_id}:embedContent"
        payload = {
            "model": f"models/{model_id}",
            "content": {
                "parts": [{"text": text}]
            }
        }
        
        try:
            logger.debug("Sending embedding request to Gemini: %s", model_id)
            response = requests.post(url, json=payload, timeout=self._timeout, headers={"x-goog-api-key": self._api_key})
            
            if response.status_code in (401, 403):
                raise ProviderAuthenticationError("Invalid API key or unauthorized access")
                
            response.raise_for_status()
            data = response.json()
            
            latency_ms = int((time.time() - start_time) * 1000)
            
            embedding = data.get("embedding", {})
            vector = embedding.get("values", [])
            
            return EmbeddingResponse(
                vector=vector,
                dimensions=len(vector),
                provider_id=self.provider_id,
                model_id=model_id,
                latency_ms=latency_ms
            )
            
        except requests.exceptions.Timeout as e:
            logger.error("Gemini embedding request timed out: %s", e)
            raise ProviderTimeoutError(f"Gemini request timed out: {e}") from e
        except requests.exceptions.ConnectionError as e:
            logger.error("Failed to connect to Gemini: %s", e)
            raise ProviderConnectionError(f"Failed to connect to Gemini API: {e}") from e
        except requests.exceptions.RequestException as e:
            logger.error("Gemini API error: %s", e)
            raise ProviderAPIError(f"Gemini API error: {e}") from e

    def health_check(self) -> ProviderHealthStatus:
        if not self._api_key:
            return ProviderHealthStatus.UNAVAILABLE
        
        url = f"{self._base_url}/{self._default_model}"
        try:
            response = requests.get(url, timeout=5, headers={"x-goog-api-key": self._api_key})
            if response.status_code == 200:
                return ProviderHealthStatus.HEALTHY
            elif response.status_code in (401, 403):
                return ProviderHealthStatus.UNAVAILABLE
            return ProviderHealthStatus.DEGRADED
        except Exception:
            logger.exception("Gemini health check failed")
            return ProviderHealthStatus.DEGRADED

    def shutdown(self) -> None:
        logger.info("Shutting down %s provider", self.display_name)
        self._is_initialized = False

    def estimate_embedding_cost(
        self, input_tokens: int, model_id: str | None = None
    ) -> float | None:
        """Estimate standard text embedding cost from published pricing."""
        model = (model_id or self._default_embed_model).lower()
        if model == "gemini-embedding-2":
            return max(0, input_tokens) * 0.20 / 1_000_000
        return None

    def estimate_cost(
        self,
        input_tokens: int,
        output_tokens: int,
        model_id: str | None = None,
    ) -> float | None:
        """Return a conservative estimate using published non-promotional rates.

        Prices can change. Unknown models intentionally return None so budget-aware
        routing will not treat an unknown cloud model as free.
        """
        model = (model_id or self._default_model).lower()
        # Standard rates effective after the currently advertised introductory
        # period, rounded up to avoid choosing a cloud model on an underpriced estimate.
        if "gemini-4-argon" in model:
            input_rate, output_rate = 4.00, 20.00
        elif "gemini-3.8-flash" in model:
            input_rate, output_rate = 1.50, 7.50
        elif "gemini-3.5-flash-lite" in model:
            input_rate, output_rate = 0.30, 2.50
        else:
            return None
        return (input_tokens * input_rate + output_tokens * output_rate) / 1_000_000

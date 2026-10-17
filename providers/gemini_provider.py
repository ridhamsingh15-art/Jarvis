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
        self._default_model = self._config.get("default_model", "gemini-1.5-pro-latest")
        self._default_embed_model = self._config.get("default_embedding_model", "text-embedding-004")
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
            Capability.REASONING,
            Capability.VISION,
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

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        requirements: InferenceRequirements | None = None,
    ) -> ModelResponse:
        if not self._is_initialized:
            self.initialize()
            
        model_id = self._default_model
        if requirements and requirements.prefer_provider == self.provider_id:
            pass
            
        start_time = time.time()
        url = f"{self._base_url}/{model_id}:generateContent?key={self._api_key}"
        
        payload = {
            "contents": [
                {"role": "user", "parts": [{"text": user_prompt}]}
            ],
            "systemInstruction": {
                "parts": [{"text": system_prompt}]
            }
        }
        
        try:
            logger.debug("Sending generation request to Gemini: %s", model_id)
            response = requests.post(url, json=payload, timeout=self._timeout)
            
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
        
        url = f"{self._base_url}/{model_id}:embedContent?key={self._api_key}"
        payload = {
            "model": f"models/{model_id}",
            "content": {
                "parts": [{"text": text}]
            }
        }
        
        try:
            logger.debug("Sending embedding request to Gemini: %s", model_id)
            response = requests.post(url, json=payload, timeout=self._timeout)
            
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
        
        url = f"{self._base_url}/{self._default_model}?key={self._api_key}"
        try:
            response = requests.get(url, timeout=5)
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

    def estimate_cost(
        self,
        input_tokens: int,
        output_tokens: int,
        model_id: str | None = None,
    ) -> float:
        model = model_id or self._default_model
        if "pro" in model.lower():
            return (input_tokens * 3.5 / 1000000) + (output_tokens * 10.5 / 1000000)
        elif "flash" in model.lower():
            return (input_tokens * 0.075 / 1000000) + (output_tokens * 0.30 / 1000000)
        return 0.0

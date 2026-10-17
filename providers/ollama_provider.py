"""
Ollama local provider implementation.
"""

import logging
import time
from typing import Any

import requests

from config.providers import PROVIDER_CONFIG
from providers.base_provider import BaseProvider
from providers.capabilities import Capability
from providers.provider_exceptions import (
    ProviderAPIError,
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


class OllamaProvider(BaseProvider):
    """Ollama local AI provider implementation."""

    def __init__(self, config: dict[str, Any] | None = None):
        self._config = config or PROVIDER_CONFIG.get("ollama", {})
        self._base_url = self._config.get("base_url", "http://localhost:11434")
        self._default_model = self._config.get("default_model", "qwen3:8b")
        self._default_embed_model = self._config.get("default_embedding_model", "nomic-embed-text")
        self._timeout = float(self._config.get("timeout_seconds", 30))
        self._max_retries = int(self._config.get("max_retries", 3))
        self._retry_backoff_seconds = float(
            self._config.get("retry_backoff_seconds", 1.0)
        )
        self._num_ctx = self._config.get("num_ctx")
        if self._num_ctx is not None:
            self._num_ctx = int(self._num_ctx)
        self._num_predict = self._config.get("num_predict")
        if self._num_predict is not None:
            self._num_predict = int(self._num_predict)
        self._keep_alive = self._config.get("keep_alive")
        self._models = dict(self._config.get("models", {}))
        self._models.setdefault("general", self._default_model)
        self._models.setdefault("reasoning", "deepseek-r1:8b")
        self._models.setdefault("coding", "qwen2.5-coder:7b")
        self._models.setdefault("vision", "qwen2.5vl:7b")
        self._models.setdefault("fast", "gemma4:e4b")

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
            Capability.CODING,
            Capability.REASONING,
            Capability.VISION,
            Capability.EMBEDDINGS,
            Capability.TOOL_USE,
        ])

    @property
    def is_local(self) -> bool:
        return True

    def initialize(self) -> None:
        logger.info("Initializing %s provider at %s", self.display_name, self._base_url)

    def _resolve_model(self, requirements: InferenceRequirements | None) -> str:
        """Resolve the model tag to use based on requirements, roles, and capabilities."""
        if not requirements:
            return self._models.get("general", self._default_model)

        # 1. Direct explicit model override
        if getattr(requirements, "prefer_model", None):
            return requirements.prefer_model

        # 2. Semantic role requested directly
        if getattr(requirements, "role", None):
            role = str(requirements.role).lower()
            if role in self._models:
                return self._models[role]

        # 3. Capability-based mapping
        caps = requirements.capabilities or frozenset()
        if Capability.CODING in caps:
            return self._models.get("coding", self._default_model)
        if Capability.REASONING in caps:
            return self._models.get("reasoning", self._default_model)
        if Capability.VISION in caps:
            return self._models.get("vision", self._default_model)

        # 4. Complexity / latency tier
        if getattr(requirements, "task_complexity", None) in ("SIMPLE", 1, 2, 3):
            return self._models.get("fast", self._models.get("general", self._default_model))

        return self._models.get("general", self._default_model)

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        requirements: InferenceRequirements | None = None,
    ) -> ModelResponse:
        model_id = self._resolve_model(requirements)
        start_time = time.time()
        
        url = f"{self._base_url}/api/chat"
        options: dict[str, Any] = {}
        if self._num_ctx is not None:
            options["num_ctx"] = self._num_ctx
        if self._num_predict is not None:
            options["num_predict"] = self._num_predict
        if requirements and getattr(requirements, "min_context_length", None):
            options["num_ctx"] = max(options.get("num_ctx", 0), requirements.min_context_length)

        payload: dict[str, Any] = {
            "model": model_id,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "stream": False
        }
        if options:
            payload["options"] = options
        if self._keep_alive is not None:
            payload["keep_alive"] = self._keep_alive
        
        try:
            logger.debug("Sending generation request to Ollama: %s", model_id)
            try:
                data = self._post_json(url, payload, "generation")
            except Exception as exc:
                fallback_model = self._models.get("general", self._default_model)
                if model_id != fallback_model:
                    logger.warning(
                        "Model %s failed: %s. Attempting fallback to general model %s",
                        model_id, exc, fallback_model
                    )
                    payload["model"] = fallback_model
                    model_id = fallback_model
                    data = self._post_json(url, payload, "generation")
                else:
                    raise
            
            latency_ms = int((time.time() - start_time) * 1000)
            
            input_tokens = data.get("prompt_eval_count", 0)
            output_tokens = data.get("eval_count", 0)
            token_usage = TokenUsage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=input_tokens + output_tokens
            )
            
            message_content = data.get("message", {}).get("content", "")
            return ModelResponse(
                text=message_content,
                provider_id=self.provider_id,
                model_id=model_id,
                latency_ms=latency_ms,
                token_usage=token_usage,
                cost=0.0
            )
            
        except requests.exceptions.Timeout as exc:
            raise ProviderTimeoutError(
                f"Ollama generation timed out after {self._max_retries + 1} attempt(s)."
            ) from exc
        except requests.exceptions.ConnectionError as exc:
            raise ProviderConnectionError(f"Failed to connect to Ollama at {self._base_url}") from exc
        except requests.exceptions.RequestException as exc:
            raise ProviderAPIError(f"Ollama API error: {exc}") from exc

    def embed(
        self,
        text: str,
        requirements: InferenceRequirements | None = None,
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
            data = self._post_json(url, payload, "embedding")
            
            latency_ms = int((time.time() - start_time) * 1000)
            vector = data.get("embedding", [])
            
            return EmbeddingResponse(
                vector=vector,
                dimensions=len(vector),
                provider_id=self.provider_id,
                model_id=model_id,
                latency_ms=latency_ms
            )
            
        except requests.exceptions.Timeout as exc:
            raise ProviderTimeoutError(
                f"Ollama embedding timed out after {self._max_retries + 1} attempt(s)."
            ) from exc
        except requests.exceptions.ConnectionError as exc:
            raise ProviderConnectionError(f"Failed to connect to Ollama at {self._base_url}") from exc
        except requests.exceptions.RequestException as exc:
            raise ProviderAPIError(f"Ollama API error: {exc}") from exc

    def _post_json(self, url: str, payload: dict[str, Any], operation: str) -> dict[str, Any]:
        """POST to Ollama with configurable retry and exponential backoff."""
        for attempt in range(self._max_retries + 1):
            timeout = self._timeout * (2**attempt)
            try:
                response = requests.post(url, json=payload, timeout=timeout)
                response.raise_for_status()
                return response.json()
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
                if attempt >= self._max_retries:
                    raise
                delay = self._retry_backoff_seconds * (2**attempt)
                logger.warning(
                    "Ollama %s attempt %d/%d failed (%s); retrying in %.1fs.",
                    operation, attempt + 1, self._max_retries + 1, exc, delay,
                )
                if delay > 0:
                    time.sleep(delay)
        raise RuntimeError("Unreachable retry loop exit")

    def health_check(self) -> ProviderHealthStatus:
        url = f"{self._base_url}/api/tags"
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                return ProviderHealthStatus.HEALTHY
            return ProviderHealthStatus.DEGRADED
        except Exception:
            logger.exception("Ollama health check failed")
            return ProviderHealthStatus.UNAVAILABLE

    def get_configured_models(self) -> dict[str, str]:
        """Return configured semantic role mapping."""
        return dict(self._models)

    def list_installed_models(self) -> list[dict[str, Any]]:
        """List models currently installed in Ollama via /api/tags."""
        url = f"{self._base_url}/api/tags"
        try:
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                return resp.json().get("models", [])
            return []
        except Exception as exc:
            logger.warning("Failed to query Ollama installed models: %s", exc)
            return []

    def shutdown(self) -> None:
        logger.info("Shutting down %s provider", self.display_name)

    def estimate_cost(
        self,
        input_tokens: int,
        output_tokens: int,
        model_id: str | None = None,
    ) -> float:
        return 0.0

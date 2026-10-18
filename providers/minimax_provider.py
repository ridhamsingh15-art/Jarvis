"""MiniMax text-generation provider using its official REST API."""

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


class MiniMaxProvider(BaseProvider):
    """MiniMax chat provider, enabled only when ``MINIMAX_API_KEY`` is set."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self._config = config or PROVIDER_CONFIG["minimax"]
        self._api_key = self._config.get("api_key") or os.environ.get("MINIMAX_API_KEY")
        self._base_url = self._config.get("base_url", "https://api.minimax.io").rstrip(
            "/"
        )
        self._default_model = self._config.get("default_model", "MiniMax-M2.7")
        self._models = dict(self._config.get("models", {}))
        self._models.setdefault("general", self._default_model)
        self._timeout = float(self._config.get("timeout_seconds", 30))
        self._is_initialized = False

    @property
    def provider_id(self) -> str:
        return "minimax"

    @property
    def display_name(self) -> str:
        return "MiniMax"

    @property
    def capabilities(self) -> frozenset[Capability]:
        return frozenset({Capability.CHAT, Capability.REASONING, Capability.TOOL_USE})

    @property
    def is_local(self) -> bool:
        return False

    def initialize(self) -> None:
        if not self._api_key:
            raise ProviderConfigurationError(
                "MiniMax API key not found in config or environment"
            )
        self._is_initialized = True

    def _resolve_model(self, requirements: InferenceRequirements | None) -> str:
        """Select a configured MiniMax model for the requested semantic role."""
        if requirements and requirements.prefer_model:
            return requirements.prefer_model
        if requirements and requirements.role:
            model = self._models.get(str(requirements.role).lower())
            if model:
                return model
        if requirements:
            if Capability.CODING in requirements.capabilities:
                return self._models.get("coding", self._default_model)
            if Capability.REASONING in requirements.capabilities:
                return self._models.get("reasoning", self._default_model)
            if requirements.task_complexity in {"SIMPLE", 1, 2, 3}:
                return self._models.get("fast", self._default_model)
        return self._models.get("general", self._default_model)

    def context_window_tokens(
        self, requirements: InferenceRequirements | None = None
    ) -> int | None:
        model = self._resolve_model(requirements).lower()
        if model in {"minimax-m2.7", "minimax-m2.7-highspeed"}:
            return 200_000
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
        started_at = time.monotonic()
        try:
            response = requests.post(
                f"{self._base_url}/v1/text/chatcompletion_v2",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={
                    "model": model_id,
                    "stream": False,
                    **(
                        {"max_tokens": requirements.max_output_tokens}
                        if requirements and requirements.max_output_tokens is not None
                        else {}
                    ),
                    "messages": [
                        {"role": "system", "name": "JARVIS", "content": system_prompt},
                        {"role": "user", "name": "user", "content": user_prompt},
                    ],
                },
                timeout=self._timeout,
            )
            if response.status_code in {401, 403}:
                raise ProviderAuthenticationError(
                    "Invalid MiniMax API key or unauthorized access"
                )
            response.raise_for_status()
            data = response.json()
        except requests.Timeout as exc:
            raise ProviderTimeoutError(
                "MiniMax request timed out. Please try again."
            ) from exc
        except requests.ConnectionError as exc:
            raise ProviderConnectionError("Failed to connect to MiniMax.") from exc
        except requests.RequestException as exc:
            raise ProviderAPIError("MiniMax could not complete the request.") from exc

        choices = data.get("choices", [])
        message = choices[0].get("message", {}) if choices else {}
        text = message.get("content", "")
        usage = data.get("usage", {})
        input_tokens = int(usage.get("prompt_tokens", 0))
        output_tokens = int(usage.get("completion_tokens", 0))
        return ModelResponse(
            text=text,
            provider_id=self.provider_id,
            model_id=model_id,
            latency_ms=int((time.monotonic() - started_at) * 1000),
            token_usage=TokenUsage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=int(
                    usage.get("total_tokens", input_tokens + output_tokens)
                ),
            ),
            cost=self.estimate_cost(input_tokens, output_tokens, model_id),
        )

    def embed(
        self,
        text: str,
        requirements: InferenceRequirements | None = None,
    ) -> EmbeddingResponse:
        del text, requirements
        raise ProviderAPIError(
            "MiniMax embeddings are not configured for this provider."
        )

    def health_check(self) -> ProviderHealthStatus:
        if not self._api_key:
            return ProviderHealthStatus.UNAVAILABLE
        try:
            response = requests.get(
                f"{self._base_url}/v1/models",
                headers={"Authorization": f"Bearer {self._api_key}"},
                timeout=min(self._timeout, 5),
            )
        except requests.RequestException:
            return ProviderHealthStatus.UNAVAILABLE
        return (
            ProviderHealthStatus.HEALTHY
            if response.ok
            else ProviderHealthStatus.DEGRADED
        )

    def shutdown(self) -> None:
        self._is_initialized = False

    def estimate_embedding_cost(
        self, input_tokens: int, model_id: str | None = None
    ) -> float | None:
        del input_tokens, model_id
        return None

    def estimate_cost(
        self, input_tokens: int, output_tokens: int, model_id: str | None = None
    ) -> float | None:
        model = (model_id or self._default_model).lower()
        if model.endswith("-highspeed"):
            input_rate, output_rate = 0.60, 2.40
        elif model in {"minimax-m2.7", "minimax-m2.7-highspeed"}:
            input_rate, output_rate = 0.30, 1.20
        else:
            return None
        return (input_tokens * input_rate + output_tokens * output_rate) / 1_000_000

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

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        requirements: InferenceRequirements | None = None,
    ) -> ModelResponse:
        del requirements
        if not self._is_initialized:
            self.initialize()

        started_at = time.monotonic()
        try:
            response = requests.post(
                f"{self._base_url}/v1/text/chatcompletion_v2",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={
                    "model": self._default_model,
                    "stream": False,
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
            model_id=self._default_model,
            latency_ms=int((time.monotonic() - started_at) * 1000),
            token_usage=TokenUsage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=int(
                    usage.get("total_tokens", input_tokens + output_tokens)
                ),
            ),
            cost=0.0,
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

    def estimate_cost(
        self, input_tokens: int, output_tokens: int, model_id: str | None = None
    ) -> float:
        del input_tokens, output_tokens, model_id
        return 0.0

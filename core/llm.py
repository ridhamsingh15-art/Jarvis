"""
Provider-neutral LLM client.

Runtime callers use the shared provider gateway for generation and embeddings.
A direct Ollama-only path remains available explicitly for isolated diagnostics.
"""

import logging

from ollama import RequestError, ResponseError, chat, embeddings

from config.config import JarvisConfig
from core.exceptions import LLMConnectionError
from providers.capabilities import Capability
from providers.provider_models import InferenceRequirements, RouterError

logger = logging.getLogger(__name__)


class LLMClient:
    """Compatibility wrapper that routes application calls through ModelGateway.

    Args:
        config: Validated provider/model configuration.
        gateway: Optional already-built gateway. If omitted, construct the same
            runtime provider strategy used by the main application.
        direct_ollama: Explicit diagnostic escape hatch for a standalone Ollama
            client. It is rejected for cloud-primary configurations.
    """

    def __init__(
        self,
        config: JarvisConfig,
        gateway=None,
        *,
        direct_ollama: bool = False,
    ) -> None:
        self._model = config.model
        self._embedding_model = config.embedding_model
        self._host = config.ollama_host
        if direct_ollama and gateway is not None:
            raise ValueError("direct_ollama=True cannot be combined with a gateway")
        if direct_ollama and config.provider != "ollama":
            raise ValueError("Direct Ollama mode requires JARVIS_PROVIDER=ollama")
        if gateway is None and not direct_ollama:
            from providers.runtime_setup import build_model_gateway

            gateway = build_model_gateway(config)
        self._gateway = gateway

    def get_embeddings(
        self, text: str, *, requirements: InferenceRequirements | None = None
    ) -> list[float]:
        """Get vector embeddings for a given text using Ollama.
        
        Args:
            text: The input string.
            
        Returns:
            List of floats representing the embedding vector.
        """
        if self._gateway is not None:
            try:
                embed_requirements = requirements or InferenceRequirements(
                    capabilities=frozenset([Capability.EMBEDDINGS]),
                    prefer_local=True,
                )
                response = self._gateway.embed(text, requirements=embed_requirements)
                return response.vector
            except RouterError as exc:
                logger.error("Model gateway embedding failed (%s)", type(exc).__name__)
                raise LLMConnectionError(
                    f"Configured model providers could not create embeddings ({type(exc).__name__})."
                ) from exc

        try:
            # Backward-compatible standalone path for callers not wired into the runtime gateway.
            resp = embeddings(model=self._embedding_model, prompt=text)
            return resp.embedding
        except RequestError as exc:
            logger.error("Ollama connection failed for embeddings: %s", exc)
            raise LLMConnectionError(f"Cannot reach Ollama: {exc}") from exc
        except ResponseError as exc:
            logger.error("Ollama response error for embeddings: %s", exc)
            # If the embedding model isn't pulled, this might throw
            raise LLMConnectionError(f"Ollama returned an error: {exc}") from exc

    def generate(
        self, system_prompt: str, user_prompt: str, *,
        requirements: InferenceRequirements | None = None,
    ) -> str:
        """Send prompts to Ollama and return the raw response text.

        Args:
            system_prompt: System-level instructions for the model.
            user_prompt: The user's natural language input.

        Returns:
            Raw text response from the model.

        Raises:
            LLMConnectionError: If Ollama is unreachable or returns
                an API error.
        """
        if self._gateway is not None:
            try:
                route_requirements = requirements or InferenceRequirements(
                    capabilities=frozenset([Capability.CHAT]),
                    role="general",
                    prefer_local=True,
                )
                response = self._gateway.generate(
                    system_prompt, user_prompt, requirements=route_requirements
                )
                return response.text
            except RouterError as exc:
                logger.error("Model gateway generation failed (%s)", type(exc).__name__)
                raise LLMConnectionError(
                    f"Configured model providers could not generate a response ({type(exc).__name__})."
                ) from exc

        if requirements is not None:
            raise LLMConnectionError(
                "Role-specific inference requirements require the shared model gateway."
            )

        logger.debug("LLM request | model=%s", self._model)

        try:
            response = chat(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
        except RequestError as exc:
            logger.error("Ollama connection failed: %s", exc)
            raise LLMConnectionError(
                f"Cannot reach Ollama at {self._host}: {exc}"
            ) from exc
        except ResponseError as exc:
            logger.error("Ollama response error: %s", exc)
            raise LLMConnectionError(
                f"Ollama returned an error: {exc}"
            ) from exc

        raw_text = response.message.content or ""
        logger.debug("LLM response length: %d chars", len(raw_text))

        return raw_text

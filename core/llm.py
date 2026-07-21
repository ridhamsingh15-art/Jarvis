"""
LLM client — pure I/O boundary to Ollama.

This module ONLY sends prompts to Ollama and returns raw text.
No parsing, no normalizing, no planning logic. The Planner
calls this module and handles everything downstream.
"""

import logging

from ollama import chat, ResponseError, RequestError

from config.config import JarvisConfig
from core.exceptions import LLMConnectionError

logger = logging.getLogger(__name__)


class LLMClient:
    """Thin wrapper around Ollama chat API.

    Responsibilities:
        - Send system + user prompts to the configured model
        - Return the raw text response
        - Wrap connection failures in LLMConnectionError
    """

    def __init__(self, config: JarvisConfig) -> None:
        self._model = config.model
        self._host = config.ollama_host

    def generate(self, system_prompt: str, user_prompt: str) -> str:
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

        raw_text = response.message.content
        logger.debug("LLM response length: %d chars", len(raw_text))

        return raw_text

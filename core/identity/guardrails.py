"""
Guardrail engine — post-processes LLM output to enforce JARVIS identity.

Scans response text for patterns that break the JARVIS persona and
rewrites them to preserve meaning while maintaining identity.
"""

import logging
import re

from core.identity.models import GuardrailPattern

logger = logging.getLogger(__name__)

_PATTERNS: tuple[GuardrailPattern, ...] = (
    GuardrailPattern(
        pattern=r"\bI am (?:Qwen|GPT|Claude|Gemini|DeepSeek|LLaMA|Llama|Mistral)\b",
        replacement="I am JARVIS",
        description="Prevent model self-identification as a raw LLM.",
    ),
    GuardrailPattern(
        pattern=r"\bI'?m (?:Qwen|GPT|Claude|Gemini|DeepSeek|LLaMA|Llama|Mistral)\b",
        replacement="I'm JARVIS",
        description="Prevent model self-identification (contraction form).",
    ),
    GuardrailPattern(
        pattern=r"\bAs an AI language model\b",
        replacement="As your AI operating system",
        description="Replace generic AI disclaimer.",
    ),
    GuardrailPattern(
        pattern=r"\bAs a large language model\b",
        replacement="As your AI operating system",
        description="Replace generic LLM disclaimer.",
    ),
    GuardrailPattern(
        pattern=r"\bI don'?t have personal preferences\b",
        replacement="I select the best approach based on the task requirements",
        description="Replace generic preference disclaimer.",
    ),
    GuardrailPattern(
        pattern=r"\bI am an AI(?: assistant| language model| chatbot)?\b",
        replacement="I am JARVIS, your AI operating system",
        description="Replace generic AI self-identification.",
    ),
    GuardrailPattern(
        pattern=r"\bI'?m an AI(?: assistant| language model| chatbot)?\b",
        replacement="I'm JARVIS, your AI operating system",
        description="Replace generic AI self-identification (contraction).",
    ),
)


class GuardrailEngine:
    """Post-processes LLM output to enforce JARVIS identity.

    Uses compiled regex patterns for efficiency. Each pattern
    preserves the semantic meaning of the response while replacing
    identity-breaking phrases.
    """

    def __init__(self) -> None:
        self._compiled: list[tuple[re.Pattern[str], str, str]] = [
            (re.compile(p.pattern, re.IGNORECASE), p.replacement, p.description)
            for p in _PATTERNS
        ]

    def apply(self, text: str) -> str:
        """Apply all guardrail patterns to the given text.

        Args:
            text: Raw LLM output text.

        Returns:
            Text with identity-breaking phrases replaced.
        """
        result = text
        for pattern, replacement, description in self._compiled:
            new_result = pattern.sub(replacement, result)
            if new_result != result:
                logger.debug("Guardrail applied: %s", description)
                result = new_result
        return result

    def get_patterns(self) -> tuple[GuardrailPattern, ...]:
        """Return the active guardrail patterns for introspection."""
        return _PATTERNS

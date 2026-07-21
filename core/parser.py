"""
JSON parser for LLM output.

Extracts structured JSON from raw LLM text that may contain
markdown fences, thinking blocks, or other noise. This module
is purely syntactic — no business logic, no normalization.
"""

import json
import re

from core.exceptions import ParseError

# Pattern to match Qwen3 thinking blocks
_THINK_PATTERN = re.compile(r"<think>.*?</think>", re.DOTALL)

# Pattern to match markdown code fences
_FENCE_PATTERN = re.compile(r"```(?:json)?\s*", re.IGNORECASE)

# Pattern to find first JSON object or array
_JSON_PATTERN = re.compile(r"(\{.*\}|\[.*\])", re.DOTALL)


def parse_json(text: str) -> dict | list[dict]:
    """Extract and parse JSON from raw LLM output.

    Handles common LLM quirks:
        - Strips <think>...</think> blocks (Qwen3)
        - Removes markdown code fences
        - Extracts the first JSON object or array

    Args:
        text: Raw text from the LLM.

    Returns:
        Parsed Python dict or list of dicts.

    Raises:
        ParseError: If no valid JSON can be extracted.
    """
    # Strip thinking blocks
    cleaned = _THINK_PATTERN.sub("", text)

    # Strip markdown code fences
    cleaned = _FENCE_PATTERN.sub("", cleaned)
    cleaned = cleaned.replace("```", "")

    # Trim whitespace
    cleaned = cleaned.strip()

    # Find first JSON structure
    match = _JSON_PATTERN.search(cleaned)

    if not match:
        raise ParseError(
            f"No JSON found in LLM output: {text[:200]}"
        )

    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        raise ParseError(
            f"Malformed JSON in LLM output: {exc}"
        ) from exc

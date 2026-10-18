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

    # Decode from the first object/array boundary. raw_decode consumes exactly
    # one JSON value, including nested objects, and ignores later trailing content.
    # Do not greedily span from the first opening delimiter to the last closing
    # delimiter: valid JSON followed by another snippet would otherwise fail.
    start = next(
        (index for index, char in enumerate(cleaned) if char in "{["),
        None,
    )
    if start is None:
        raise ParseError(f"No JSON found in LLM output: {text[:200]}")

    try:
        value, _end = json.JSONDecoder().raw_decode(cleaned, start)
        return value
    except json.JSONDecodeError as exc:
        # Fail closed on the first candidate rather than extracting a valid nested
        # object from a malformed outer payload.
        raise ParseError(f"Malformed JSON in LLM output: {exc}") from exc

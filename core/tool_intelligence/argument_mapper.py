"""
Argument Mapper — intelligently maps semantic argument names to strict schemas.
Supports tool-specific and schema-aware parameter normalization, deterministic alias mapping,
and strict ambiguity rejection.
"""

from __future__ import annotations

import logging
from typing import ClassVar

from core.exceptions import ValidationError

logger = logging.getLogger(__name__)


class ArgumentMapper:
    """Maps incorrect or aliased argument names to expected schema names with ambiguity detection."""

    # Map canonical schema argument name -> tuple of accepted alias names
    _CANONICAL_ALIASES: ClassVar[dict[str, tuple[str, ...]]] = {
        "path": ("file", "filename", "filepath", "file_path", "folder", "directory", "dir", "source", "from"),
        "dest": ("destination", "target", "to"),
        "text": ("content", "contents", "data", "body", "message"),
        "content": ("text", "contents", "data", "body", "message"),
        "query": ("search_query", "search_term", "search", "q", "term"),
        "url": ("link", "address", "webpage", "website_url"),
        "site": ("site_name", "website_name", "website"),
        "app": ("name", "program", "application", "app_name"),
        "new_name": ("new_path", "to_name", "filename"),
    }

    def map_arguments(
        self,
        raw_args: dict,
        required_args: list[str],
        optional_args: list[str] | None = None,
        tool_name: str = "",
        action_name: str = "",
    ) -> tuple[dict, int]:
        """Map raw arguments to match canonical schema arguments.

        Rules:
        1. Tool/schema-aware: maps against expected_args (required + optional).
        2. Non-destructive: if canonical argument already exists, does not modify it.
        3. Ambiguity rejection:
           - If both canonical argument AND an alias are provided: reject with ValidationError.
           - If multiple aliases mapping to the same canonical argument are provided: reject with ValidationError.
        4. Observable: logs each normalization at DEBUG/INFO.
        5. Unknown keys: preserves unknown keys so strict Validator can catch and reject them.

        Args:
            raw_args: The arguments provided by the LLM.
            required_args: Required args from ActionDefinition.
            optional_args: Optional args from ActionDefinition.
            tool_name: Name of tool for logging.
            action_name: Name of action for logging.

        Returns:
            Tuple of (normalized_arguments_dict, number_of_repairs).

        Raises:
            ValidationError: If ambiguous arguments are provided.
        """
        mapped = dict(raw_args)
        repairs = 0
        expected_args = list(required_args) + list(optional_args or [])

        # Schema-aware alias normalization
        for canonical in expected_args:
            aliases = self._CANONICAL_ALIASES.get(canonical, ())
            matching_aliases = [k for k in aliases if k in mapped and k != canonical]

            # Ambiguity Check 1: Both canonical parameter and an alias were provided
            if canonical in mapped and matching_aliases:
                logger.warning(
                    "[NORMALIZER] Ambiguous arguments for %s.%s: canonical '%s' and alias '%s' both provided",
                    tool_name, action_name, canonical, matching_aliases[0],
                )
                raise ValidationError(
                    f"Ambiguous arguments for '{tool_name}.{action_name}': "
                    f"both canonical parameter '{canonical}' and alias '{matching_aliases[0]}' were provided."
                )

            # Ambiguity Check 2: Multiple conflicting aliases provided for the same parameter
            if canonical not in mapped and len(matching_aliases) > 1:
                logger.warning(
                    "[NORMALIZER] Ambiguous arguments for %s.%s: multiple conflicting aliases %s provided for '%s'",
                    tool_name, action_name, matching_aliases, canonical,
                )
                raise ValidationError(
                    f"Ambiguous arguments for '{tool_name}.{action_name}': "
                    f"multiple conflicting aliases {matching_aliases} provided for '{canonical}'."
                )

            # Safe normalization: exactly one alias provided, canonical absent
            if canonical not in mapped and len(matching_aliases) == 1:
                chosen_alias = matching_aliases[0]
                val = mapped.pop(chosen_alias)
                mapped[canonical] = val
                repairs += 1
                logger.info(
                    "[NORMALIZER] Normalized parameter '%s' -> '%s' for %s.%s",
                    chosen_alias, canonical, tool_name or "tool", action_name or "action",
                )

        # Fallback: if exactly 1 argument provided and exactly 1 argument required (no optional args),
        # and the key doesn't match any expected arg, map it unconditionally as a hallucinated single key.
        if len(mapped) == 1 and len(required_args) == 1 and not (optional_args or []):
            only_key = next(iter(mapped.keys()))
            only_needed = required_args[0]
            if only_key != only_needed and only_key not in expected_args:
                val = mapped.pop(only_key)
                mapped[only_needed] = val
                repairs += 1
                logger.info(
                    "[NORMALIZER] Fallback 1-to-1 parameter '%s' -> '%s' for %s.%s",
                    only_key, only_needed, tool_name or "tool", action_name or "action",
                )

        return mapped, repairs

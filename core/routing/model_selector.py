"""
Task-based Model Selector and Router for JARVIS.

Determines the optimal model role and inference requirements based on the user's
request, semantic intent, and task characteristics.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from providers.capabilities import Capability
from providers.provider_models import InferenceRequirements

logger = logging.getLogger(__name__)


class TaskModelSelector:
    """Classifies incoming tasks into model roles and builds InferenceRequirements."""

    # Regex patterns for deterministic role matching
    _VISION_PATTERN = re.compile(
        r"\b(?:screenshot|image|picture|photo|diagram|look\s+at\s+(?:this|the)|inspect\s+(?:the\s+)?screen|visual)\b",
        re.IGNORECASE,
    )

    _CODING_PATTERN = re.compile(
        r"\b(?:debug|python|code|script|traceback|syntax\s+error|exception|function|class|"
        r"refactor|bug|algorithm|c\+\+|javascript|typescript|regex|stack\s*trace|fix\s+(?:this\s+)?(?:error|bug)|"
        r"write\s+(?:a\s+)?(?:function|script|program|class)|unit\s+test|sql|query)\b"
        r"|(?:def\s+[a-zA-Z_]\w*\s*\(|import\s+[a-zA-Z_]|const\s+[a-zA-Z_]|```(?:python|bash|sh|js|ts|cpp|java))",
        re.IGNORECASE,
    )

    _REASONING_PATTERN = re.compile(
        r"\b(?:solve(?:\s+this)?|mathematical|math\s+problem|equation|theorem|calculate|"
        r"prove\s+that|proof|derivation|step\s*by\s*step\s+reasoning|logical\s+deduction|"
        r"logic\s+puzzle|probability|integral|derivative|calculus|algebra|physics\s+problem)\b",
        re.IGNORECASE,
    )

    _FAST_TOOL_PATTERN = re.compile(
        r"^(?:please\s+|can\s+you\s+|could\s+you\s+)?"
        r"(?:open|launch|start|close|run)\s+(?:the\s+)?(?:calculator|calc|notepad|browser|chrome|terminal|cmd)\b.*",
        re.IGNORECASE,
    )

    def __init__(self, default_role: str = "general") -> None:
        self._default_role = default_role

    def select_requirements(
        self,
        user_input: str,
        explicit_role: str | None = None,
        prefer_model: str | None = None,
    ) -> InferenceRequirements:
        """Analyze user input and determine the appropriate InferenceRequirements.

        Args:
            user_input: The user's prompt or instruction.
            explicit_role: Optional explicit role override ('general', 'coding', 'reasoning', 'vision', 'fast').
            prefer_model: Optional specific model tag override.

        Returns:
            InferenceRequirements configured with capabilities, role, and hints.
        """
        if explicit_role:
            role = explicit_role.lower()
            return self._build_reqs_for_role(role, prefer_model=prefer_model)

        cleaned = user_input.strip()

        # 1. Vision check
        if self._VISION_PATTERN.search(cleaned):
            logger.info("[MODEL ROUTER] Task classified as VISION -> Role: vision")
            return self._build_reqs_for_role("vision", prefer_model=prefer_model)

        # 2. Coding check
        if self._CODING_PATTERN.search(cleaned):
            logger.info("[MODEL ROUTER] Task classified as CODING -> Role: coding")
            return self._build_reqs_for_role("coding", prefer_model=prefer_model)

        # 3. Reasoning check
        if self._REASONING_PATTERN.search(cleaned):
            logger.info("[MODEL ROUTER] Task classified as REASONING -> Role: reasoning")
            return self._build_reqs_for_role("reasoning", prefer_model=prefer_model)

        # 4. Fast Tool check
        if self._FAST_TOOL_PATTERN.match(cleaned):
            logger.info("[MODEL ROUTER] Task classified as FAST_TOOL -> Role: fast")
            return self._build_reqs_for_role("fast", prefer_model=prefer_model)

        # 5. Default General
        logger.info("[MODEL ROUTER] Task classified as GENERAL -> Role: general")
        return self._build_reqs_for_role("general", prefer_model=prefer_model)

    def _build_reqs_for_role(
        self, role: str, prefer_model: str | None = None
    ) -> InferenceRequirements:
        """Construct InferenceRequirements for a specific semantic role."""
        if role == "coding":
            return InferenceRequirements(
                capabilities=frozenset([Capability.CODING]),
                role="coding",
                task_complexity="COMPLEX",
                prefer_local=True,
                prefer_model=prefer_model,
            )
        if role == "reasoning":
            return InferenceRequirements(
                capabilities=frozenset([Capability.REASONING]),
                role="reasoning",
                task_complexity="COMPLEX",
                prefer_local=True,
                prefer_model=prefer_model,
            )
        if role == "vision":
            return InferenceRequirements(
                capabilities=frozenset([Capability.VISION]),
                role="vision",
                task_complexity="MODERATE",
                prefer_local=True,
                prefer_model=prefer_model,
            )
        if role == "fast":
            return InferenceRequirements(
                capabilities=frozenset([Capability.TOOL_USE, Capability.CHAT]),
                role="fast",
                task_complexity="SIMPLE",
                prefer_local=True,
                prefer_model=prefer_model,
            )

        # Default general role
        return InferenceRequirements(
            capabilities=frozenset([Capability.CHAT]),
            role="general",
            task_complexity="MODERATE",
            prefer_local=True,
            prefer_model=prefer_model,
        )

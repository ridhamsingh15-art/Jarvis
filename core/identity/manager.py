"""
Identity Manager — public facade for the JARVIS identity subsystem.

This is the ONLY class that ConversationEngine and Planner should
depend on for identity-related concerns. It composes Persona,
PromptBuilder, GuardrailEngine, and IdentityContextBuilder internally.
"""

import logging
import functools

from core.cognition.dialogue import DialogueState
from core.cognition.context_models import ContextPackage
from core.identity.context import IdentityContextBuilder
from core.identity.guardrails import GuardrailEngine
from core.identity.models import IdentityContext
from core.identity.persona import Persona
from core.identity.prompt_builder import PromptBuilder

logger = logging.getLogger(__name__)


class IdentityManager:
    """Public facade for all JARVIS identity operations.

    Consumers call:
        build_system_prompt(state, tools_info)  — for ConversationEngine
        build_planner_prompt(tool_descriptions, context) — for Planner
        apply_guardrails(text) — for post-processing LLM output
    """

    def __init__(self, active_model: str, active_provider: str) -> None:
        self._persona = Persona()
        self._guardrails = GuardrailEngine()
        self._context_builder = IdentityContextBuilder(
            persona=self._persona,
            active_model=active_model,
            active_provider=active_provider,
        )
        self._identity_context: IdentityContext = self._context_builder.build()
        self._prompt_builder = PromptBuilder(self._identity_context)
        logger.info(
            "IdentityManager initialized (model=%s, provider=%s)",
            active_model,
            active_provider,
        )

    def build_system_prompt(self, state: DialogueState, context_package: "ContextPackage") -> str:
        """Build the complete system prompt for the ConversationEngine."""
        # Using a simple hash caching mechanism directly since state/context might not be hashable by functools
        return self._prompt_builder.build_conversation_prompt(state, context_package)

    @functools.lru_cache(maxsize=16)
    def build_planner_prompt(self, tool_descriptions: str, context: str) -> str:
        """Build the system prompt for the Planner.

        Args:
            tool_descriptions: Formatted tool descriptions from Registry.describe().
            context: Optional conversation history string.

        Returns:
            Full system prompt for the planning pipeline.
        """
        return self._prompt_builder.build_planner_prompt(tool_descriptions, context)

    def apply_guardrails(self, text: str) -> str:
        """Post-process LLM output to enforce JARVIS identity.

        Args:
            text: Raw LLM response text.

        Returns:
            Text with identity-breaking phrases replaced.
        """
        return self._guardrails.apply(text)

    def get_identity_context(self) -> IdentityContext:
        """Return the current identity context for introspection."""
        return self._identity_context

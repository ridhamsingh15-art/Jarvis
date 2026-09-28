import logging
from typing import Set, Optional, Any
from core.cognition.context_models import ProviderType
from core.reasoning.execution_plan import ExecutionPlan

logger = logging.getLogger(__name__)

# Deterministic provider sets per intent — no LLM required.
_PROVIDERS_BY_INTENT: dict[str, Set[ProviderType]] = {
    "chat":    {ProviderType.CONVERSATION, ProviderType.TOOL},
    "tool":    {ProviderType.CONVERSATION, ProviderType.TOOL},
    "memory":  {ProviderType.MEMORY, ProviderType.PKI, ProviderType.CONVERSATION},
    "mission": {
        ProviderType.MEMORY, ProviderType.PKI, ProviderType.MISSION,
        ProviderType.PROJECT, ProviderType.WORKSPACE,
        ProviderType.TOOL, ProviderType.CONVERSATION,
    },
}
_PROVIDERS_DEFAULT: Set[ProviderType] = {ProviderType.MEMORY, ProviderType.CONVERSATION, ProviderType.TOOL}


class ContextBuilder:
    """Determines which context providers to query based on ExecutionPlan or intent.

    Provider selection is fully deterministic — no LLM call is ever made here.
    """

    def determine_providers(
        self,
        plan: Optional[ExecutionPlan] = None,
        user_input: str = "",
        intent: str = "chat",
    ) -> Set[ProviderType]:
        """Return the set of context providers to query.

        Priority:
          1. If a plan is provided and carries flags, use plan-driven selection.
          2. Otherwise, use the deterministic intent-to-provider map.
          3. Fall back to the default set if intent is unrecognised.
        """
        if plan is not None and (
            plan.requires_knowledge
            or plan.required_missions
            or plan.required_tools
            or plan.requires_project
        ):
            providers: Set[ProviderType] = {ProviderType.MEMORY, ProviderType.CONVERSATION, ProviderType.TOOL}
            if plan.requires_knowledge:
                providers.add(ProviderType.PKI)
            if plan.required_missions:
                providers.add(ProviderType.MISSION)
            if plan.requires_project:
                providers.add(ProviderType.PROJECT)
                providers.add(ProviderType.WORKSPACE)
            return providers

        return _PROVIDERS_BY_INTENT.get(intent, _PROVIDERS_DEFAULT)

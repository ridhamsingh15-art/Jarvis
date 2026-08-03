import uuid
from typing import Any

from core.models.primitives import Identifier

from .dispatcher import TaskDispatcher
from .exceptions import TaskDelegationError
from .interfaces import IAgentRegistry, ICoordinator
from .models import AgentResult, AgentTask, SharedContext


class MasterCoordinator(ICoordinator):
    """Determines required capabilities and delegates workloads across specialized agents."""

    def __init__(self, registry: IAgentRegistry) -> None:
        self._registry = registry

    async def assign(self, intent: str, payload: dict[str, Any]) -> AgentResult:
        """Assigns the work to a matching agent sequentially."""
        
        # For this implementation, we map intents trivially to capabilities.
        # In a real cognitive setup, an LLM determines the capability graph dynamically.
        required_capability = self._extract_capability(intent)
        
        agents = self._registry.get_agents_by_capability(required_capability)
        if not agents:
            raise TaskDelegationError(f"No agents found for capability: {required_capability}")
            
        selected_agent = agents[0]
        
        task_id = Identifier(f"task_{uuid.uuid4().hex[:8]}")
        task = AgentTask(
            id=task_id,
            intent=intent,
            payload=payload
        )
        
        # Dispatch the task
        dummy_context = SharedContext(session_id=Identifier("session_0"))
        result = await TaskDispatcher.dispatch(selected_agent, task, dummy_context)
        return result

    def _extract_capability(self, intent: str) -> str:
        intent_lower = intent.lower()
        if "plan" in intent_lower:
            return "planning"
        if "code" in intent_lower or "write" in intent_lower:
            return "programming"
        if "search" in intent_lower or "research" in intent_lower:
            return "web_search"
        if "review" in intent_lower:
            return "code_review"
        if "test" in intent_lower:
            return "unit_testing"
        if "remember" in intent_lower or "retrieve" in intent_lower:
            return "retrieval"
            
        return "planning" # default fallback

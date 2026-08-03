from core.models.primitives import Identifier

from .agent import BaseAgent
from .enums import AgentRole, TaskState
from .models import AgentCapability, AgentProfile, AgentResult, AgentTask, SharedContext


class MemoryAgent(BaseAgent):
    """Agent responsible for state persistence mapping and retrieval."""

    def __init__(self) -> None:
        profile = AgentProfile(
            id=Identifier("agent_memory"),
            role=AgentRole.MEMORY,
            capabilities=[
                AgentCapability(name="retrieval", description="Searches vector databases."),
                AgentCapability(name="storage", description="Persists contextual memory.")
            ]
        )
        super().__init__(profile)

    async def execute(self, task: AgentTask, context: SharedContext) -> AgentResult:
        await self._simulate_work()
        
        # Mock cognitive logic
        payload = {"retrieved_data": "Historical facts."}
        return AgentResult(
            task_id=task.id,
            status=TaskState.COMPLETED,
            payload=payload
        )

from core.models.primitives import Identifier

from .agent import BaseAgent
from .enums import AgentRole, TaskState
from .models import AgentCapability, AgentProfile, AgentResult, AgentTask, SharedContext


class ResearchAgent(BaseAgent):
    """Agent responsible for gathering contextual knowledge."""

    def __init__(self) -> None:
        profile = AgentProfile(
            id=Identifier("agent_researcher"),
            role=AgentRole.RESEARCH,
            capabilities=[
                AgentCapability(name="web_search", description="Searches public web endpoints."),
                AgentCapability(name="summarization", description="Summarizes long text.")
            ]
        )
        super().__init__(profile)

    async def execute(self, task: AgentTask, context: SharedContext) -> AgentResult:
        await self._simulate_work()
        
        # Mock cognitive logic
        payload = {"summary": "Extracted research data."}
        return AgentResult(
            task_id=task.id,
            status=TaskState.COMPLETED,
            payload=payload
        )

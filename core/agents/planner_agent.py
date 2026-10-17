from core.models.primitives import Identifier

from .agent import BaseAgent
from .enums import AgentRole, TaskState
from .models import AgentCapability, AgentProfile, AgentResult, AgentTask, SharedContext


class PlannerAgent(BaseAgent):
    """Agent responsible for breaking down complex intents into plans."""

    def __init__(self) -> None:
        profile = AgentProfile(
            id=Identifier("agent_planner"),
            role=AgentRole.PLANNER,
            capabilities=[
                AgentCapability(name="planning", description="Generates step by step execution plans.")
            ]
        )
        super().__init__(profile)

    async def execute(self, task: AgentTask, context: SharedContext) -> AgentResult:
        await self._simulate_work()
        
        # Mock cognitive logic
        payload = {"plan": ["step 1", "step 2", "step 3"]}
        return AgentResult(
            task_id=task.id,
            status=TaskState.COMPLETED,
            payload=payload
        )

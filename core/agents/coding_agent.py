from core.models.primitives import Identifier

from .agent import BaseAgent
from .enums import AgentRole, TaskState
from .models import AgentCapability, AgentProfile, AgentResult, AgentTask, SharedContext


class CodingAgent(BaseAgent):
    """Agent responsible for writing executable source code."""

    def __init__(self) -> None:
        profile = AgentProfile(
            id=Identifier("agent_coder"),
            role=AgentRole.CODING,
            capabilities=[
                AgentCapability(name="programming", description="Writes production code."),
                AgentCapability(name="debugging", description="Fixes syntax bugs.")
            ]
        )
        super().__init__(profile)

    async def execute(self, task: AgentTask, context: SharedContext) -> AgentResult:
        await self._simulate_work()
        
        # Mock cognitive logic
        payload = {"code": "def hello():\n    print('world')"}
        return AgentResult(
            task_id=task.id,
            status=TaskState.COMPLETED,
            payload=payload
        )

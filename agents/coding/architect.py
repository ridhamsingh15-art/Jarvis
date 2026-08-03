
from core.agents.agent import BaseAgent
from core.agents.enums import AgentRole, TaskState
from core.agents.models import (
    AgentCapability,
    AgentProfile,
    AgentResult,
    AgentTask,
    SharedContext,
)
from core.models.primitives import Identifier


class ArchitectAgent(BaseAgent):
    """Generates high-level system designs."""


    def __init__(self) -> None:
        super().__init__(
            profile=AgentProfile(
                id=Identifier("agent_architect"),
                role=AgentRole.PLANNER,
                capabilities=[AgentCapability(name="architecture", description="architecture")]
            )
        )

    async def execute(self, task: AgentTask, context: SharedContext) -> AgentResult:
        await self._simulate_work()
        
        design = f'Architecture Design for: {task.intent}'; payload = {'design': design}
        
        return AgentResult(
            task_id=task.id,
            status=TaskState.COMPLETED,
            payload={"output": "Success", **payload}
        )

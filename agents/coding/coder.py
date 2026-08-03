
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


class CoderAgent(BaseAgent):
    """Executes specific implementation plans."""


    def __init__(self) -> None:
        super().__init__(
            profile=AgentProfile(
                id=Identifier("agent_coder"),
                role=AgentRole.CODING,
                capabilities=[AgentCapability(name="coding", description="coding")]
            )
        )

    async def execute(self, task: AgentTask, context: SharedContext) -> AgentResult:
        await self._simulate_work()
        
        design = task.payload.get('design', 'Default Design'); code = f'# Code for {design}\ndef main(): pass'; payload = {'code': code}
        
        return AgentResult(
            task_id=task.id,
            status=TaskState.COMPLETED,
            payload={"output": "Success", **payload}
        )

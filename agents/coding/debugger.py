
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


class DebuggerAgent(BaseAgent):
    """Intervenes when tests fail."""


    def __init__(self) -> None:
        super().__init__(
            profile=AgentProfile(
                id=Identifier("agent_debugger"),
                role=AgentRole.CODING,
                capabilities=[AgentCapability(name="debugging", description="debugging")]
            )
        )

    async def execute(self, task: AgentTask, context: SharedContext) -> AgentResult:
        await self._simulate_work()
        
        payload = {'patched_code': '# Patched code'}
        
        return AgentResult(
            task_id=task.id,
            status=TaskState.COMPLETED,
            payload={"output": "Success", **payload}
        )

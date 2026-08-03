
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


class DocumentationAgent(BaseAgent):
    """Generates docs."""


    def __init__(self) -> None:
        super().__init__(
            profile=AgentProfile(
                id=Identifier("agent_documentation"),
                role=AgentRole.CODING,
                capabilities=[AgentCapability(name="documentation", description="documentation")]
            )
        )

    async def execute(self, task: AgentTask, context: SharedContext) -> AgentResult:
        await self._simulate_work()
        
        payload = {'docs': '# Docs'}
        
        return AgentResult(
            task_id=task.id,
            status=TaskState.COMPLETED,
            payload={"output": "Success", **payload}
        )


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


class GitManagerAgent(BaseAgent):
    """Handles git operations."""


    def __init__(self) -> None:
        super().__init__(
            profile=AgentProfile(
                id=Identifier("agent_git"),
                role=AgentRole.CUSTOM,
                capabilities=[AgentCapability(name="git", description="git")]
            )
        )

    async def execute(self, task: AgentTask, context: SharedContext) -> AgentResult:
        await self._simulate_work()
        
        payload = {'commit_hash': 'a1b2c3'}
        
        return AgentResult(
            task_id=task.id,
            status=TaskState.COMPLETED,
            payload={"output": "Success", **payload}
        )


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


class TesterAgent(BaseAgent):
    """Writes unit tests."""

    __test__ = False

    def __init__(self) -> None:
        super().__init__(
            profile=AgentProfile(
                id=Identifier("agent_tester"),
                role=AgentRole.TESTING,
                capabilities=[AgentCapability(name="testing", description="testing")]
            )
        )

    async def execute(self, task: AgentTask, context: SharedContext) -> AgentResult:
        await self._simulate_work()
        
        payload = {'tests': 'def test_main(): pass'}
        if task.payload.get('simulate_failure'):
            return AgentResult(task_id=task.id, status=TaskState.FAILED, payload={'output': 'Tests failed'})
        
        return AgentResult(
            task_id=task.id,
            status=TaskState.COMPLETED,
            payload={"output": "Success", **payload}
        )

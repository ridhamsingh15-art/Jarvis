from core.models.primitives import Identifier

from .agent import BaseAgent
from .enums import AgentRole, TaskState
from .models import AgentCapability, AgentProfile, AgentResult, AgentTask, SharedContext


class TestingAgent(BaseAgent):
    """Agent responsible for writing and running test suites."""

    def __init__(self) -> None:
        profile = AgentProfile(
            id=Identifier("agent_tester"),
            role=AgentRole.TESTING,
            capabilities=[
                AgentCapability(name="unit_testing", description="Writes unit tests."),
                AgentCapability(name="qa", description="Quality assurance analysis.")
            ]
        )
        super().__init__(profile)

    async def execute(self, task: AgentTask, context: SharedContext) -> AgentResult:
        await self._simulate_work()
        
        # Mock cognitive logic
        payload = {"test_coverage": 100, "tests_passed": True}
        return AgentResult(
            task_id=task.id,
            status=TaskState.COMPLETED,
            payload=payload
        )

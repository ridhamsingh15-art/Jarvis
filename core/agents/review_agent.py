from core.models.primitives import Identifier

from .agent import BaseAgent
from .enums import AgentRole, TaskState
from .models import AgentCapability, AgentProfile, AgentResult, AgentTask, SharedContext


class ReviewAgent(BaseAgent):
    """Agent responsible for auditing and validating outputs."""

    def __init__(self) -> None:
        profile = AgentProfile(
            id=Identifier("agent_reviewer"),
            role=AgentRole.REVIEW,
            capabilities=[
                AgentCapability(name="code_review", description="Validates code quality."),
                AgentCapability(name="security_audit", description="Checks for vulnerabilities.")
            ]
        )
        super().__init__(profile)

    async def execute(self, task: AgentTask, context: SharedContext) -> AgentResult:
        await self._simulate_work()
        
        # Mock cognitive logic
        payload = {"approved": True, "feedback": "LGTM"}
        return AgentResult(
            task_id=task.id,
            status=TaskState.COMPLETED,
            payload=payload
        )

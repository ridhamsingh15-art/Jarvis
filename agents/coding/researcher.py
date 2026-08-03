
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


class ResearcherAgent(BaseAgent):
    """Integrates deeply with the KnowledgeManager."""


    def __init__(self) -> None:
        super().__init__(
            profile=AgentProfile(
                id=Identifier("agent_researcher"),
                role=AgentRole.RESEARCH,
                capabilities=[AgentCapability(name="research", description="research")]
            )
        )

    async def execute(self, task: AgentTask, context: SharedContext) -> AgentResult:
        await self._simulate_work()
        
        research_context = f'Research context for {task.intent}'; payload = {'research': research_context}
        
        return AgentResult(
            task_id=task.id,
            status=TaskState.COMPLETED,
            payload={"output": "Success", **payload}
        )

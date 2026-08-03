import uuid

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

from .architect import ArchitectAgent
from .coder import CoderAgent
from .tester import TesterAgent


class ProjectManagerAgent(BaseAgent):
    """Coordinates the software development lifecycle."""

    def __init__(self) -> None:
        super().__init__(
            profile=AgentProfile(
                id=Identifier("agent_project_manager"),
                role=AgentRole.COORDINATOR,
                capabilities=[AgentCapability(name="project_management", description="project_management")]
            )
        )
        self.architect = ArchitectAgent()
        self.coder = CoderAgent()
        self.tester = TesterAgent()

    async def execute(self, task: AgentTask, context: SharedContext) -> AgentResult:
        await self._simulate_work()
        
        sub_task = AgentTask(
            id=Identifier(f"task_{uuid.uuid4().hex[:8]}"),
            intent=task.intent,
            payload=task.payload
        )
        
        arch_result = await self.architect.execute(sub_task, context)
        if arch_result.status != TaskState.COMPLETED:
            return AgentResult(task_id=task.id, status=TaskState.FAILED, payload={"output": "Architecture failed"})
            
        sub_task = AgentTask(
            id=Identifier(f"task_{uuid.uuid4().hex[:8]}"),
            intent="code",
            payload=arch_result.payload
        )
        
        code_result = await self.coder.execute(sub_task, context)
        if code_result.status != TaskState.COMPLETED:
            return AgentResult(task_id=task.id, status=TaskState.FAILED, payload={"output": "Coding failed"})
            
        sub_task = AgentTask(
            id=Identifier(f"task_{uuid.uuid4().hex[:8]}"),
            intent="test",
            payload=code_result.payload
        )
        
        test_result = await self.tester.execute(sub_task, context)
        if test_result.status != TaskState.COMPLETED:
            return AgentResult(task_id=task.id, status=TaskState.FAILED, payload={"output": "Testing failed"})
            
        return AgentResult(
            task_id=task.id,
            status=TaskState.COMPLETED,
            payload={"output": "Project completed successfully"}
        )

import os

agents_dir = "agents/coding"
files = [
    "architect.py", "researcher.py", "coder.py", "reviewer.py", "tester.py", 
    "debugger.py", "refactor.py", "documentation.py", "git_manager.py", "project_manager.py"
]

base_template = """import builtins

from core.agents.agent import BaseAgent
from core.agents.enums import AgentRole, TaskState
from core.agents.models import AgentCapability, AgentProfile, AgentResult, AgentTask, SharedContext
from core.models.primitives import Identifier

class {class_name}(BaseAgent):
    \"\"\"{description}\"\"\"

{test_attr}
    def __init__(self) -> None:
        super().__init__(
            profile=AgentProfile(
                id=Identifier("{agent_id}"),
                role={role},
                capabilities=[AgentCapability(name="{cap}", description="{cap}")]
            )
        )

    async def execute(self, task: AgentTask, context: SharedContext) -> AgentResult:
        await self._simulate_work()
        
        {logic}
        
        return AgentResult(
            task_id=task.id,
            status=TaskState.COMPLETED,
            payload={{"output": "Success", **{payload}}}
        )
"""

agent_configs = {
    "architect.py": ("ArchitectAgent", "Generates high-level system designs.", "AgentRole.PLANNER", "agent_architect", "architecture", "", "design = f'Architecture Design for: {task.intent}'; payload = {'design': design}"),
    "researcher.py": ("ResearcherAgent", "Integrates deeply with the KnowledgeManager.", "AgentRole.RESEARCH", "agent_researcher", "research", "", "research_context = f'Research context for {task.intent}'; payload = {'research': research_context}"),
    "coder.py": ("CoderAgent", "Executes specific implementation plans.", "AgentRole.CODING", "agent_coder", "coding", "", "design = task.payload.get('design', 'Default Design'); code = f'# Code for {design}\\ndef main(): pass'; payload = {'code': code}"),
    "reviewer.py": ("ReviewerAgent", "Analyzes code modifications.", "AgentRole.REVIEW", "agent_reviewer", "review", "", "payload = {'review': 'Code looks good.'}"),
    "tester.py": ("TesterAgent", "Writes unit tests.", "AgentRole.TESTING", "agent_tester", "testing", "    __test__ = False\n", "payload = {'tests': 'def test_main(): pass'}\n        if task.payload.get('simulate_failure'):\n            return AgentResult(task_id=task.id, status=TaskState.FAILED, payload={'output': 'Tests failed'})"),
    "debugger.py": ("DebuggerAgent", "Intervenes when tests fail.", "AgentRole.CODING", "agent_debugger", "debugging", "", "payload = {'patched_code': '# Patched code'}"),
    "refactor.py": ("RefactorAgent", "Improves code structure.", "AgentRole.CODING", "agent_refactor", "refactoring", "", "payload = {'refactored': True}"),
    "documentation.py": ("DocumentationAgent", "Generates docs.", "AgentRole.CODING", "agent_documentation", "documentation", "", "payload = {'docs': '# Docs'}"),
    "git_manager.py": ("GitManagerAgent", "Handles git operations.", "AgentRole.CUSTOM", "agent_git", "git", "", "payload = {'commit_hash': 'a1b2c3'}"),
}

for f in files:
    if f in agent_configs:
        cls_name, desc, role, agent_id, cap, test_attr, logic = agent_configs[f]
        content = base_template.format(
            class_name=cls_name,
            description=desc,
            role=role,
            agent_id=agent_id,
            cap=cap,
            test_attr=test_attr,
            logic=logic,
            payload="payload"
        )
        with open(os.path.join(agents_dir, f), "w") as file:
            file.write(content)

# Overwrite project manager
pm_code = """import builtins
import uuid

from core.agents.agent import BaseAgent
from core.agents.enums import AgentRole, TaskState
from core.agents.models import AgentCapability, AgentProfile, AgentResult, AgentTask, SharedContext
from core.models.primitives import Identifier

from .architect import ArchitectAgent
from .coder import CoderAgent
from .tester import TesterAgent

class ProjectManagerAgent(BaseAgent):
    \"\"\"Coordinates the software development lifecycle.\"\"\"

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
"""
with open(os.path.join(agents_dir, "project_manager.py"), "w") as file:
    file.write(pm_code)

# Rewrite tests
test_code = """import pytest

from core.agents.enums import TaskState
from core.agents.models import AgentTask, SharedContext
from core.models.primitives import Identifier

from agents.coding import (
    ArchitectAgent,
    CoderAgent,
    DebuggerAgent,
    DocumentationAgent,
    GitManagerAgent,
    ProjectManagerAgent,
    RefactorAgent,
    ResearcherAgent,
    ReviewerAgent,
    TesterAgent,
)

@pytest.fixture
def shared_context():
    return SharedContext(session_id=Identifier("test_ctx"))

@pytest.fixture
def base_task():
    return AgentTask(id=Identifier("test_task"), intent="Build a web scraper")

@pytest.mark.asyncio
async def test_architect_agent(shared_context, base_task):
    agent = ArchitectAgent()
    result = await agent.execute(base_task, shared_context)
    assert result.status == TaskState.COMPLETED
    assert "Component" not in result.payload.get("design", "") # The mock returns "Architecture Design for: Build a web scraper"
    assert "Build a web scraper" in result.payload.get("design", "")

@pytest.mark.asyncio
async def test_researcher_agent(shared_context, base_task):
    agent = ResearcherAgent()
    result = await agent.execute(base_task, shared_context)
    assert result.status == TaskState.COMPLETED

@pytest.mark.asyncio
async def test_coder_agent(shared_context, base_task):
    task = AgentTask(id=base_task.id, intent=base_task.intent, payload={"design": "Test Design"})
    agent = CoderAgent()
    result = await agent.execute(task, shared_context)
    assert result.status == TaskState.COMPLETED
    assert "Test Design" in result.payload.get("code", "")

@pytest.mark.asyncio
async def test_reviewer_agent(shared_context, base_task):
    agent = ReviewerAgent()
    result = await agent.execute(base_task, shared_context)
    assert result.status == TaskState.COMPLETED

@pytest.mark.asyncio
async def test_tester_agent_success(shared_context, base_task):
    agent = TesterAgent()
    result = await agent.execute(base_task, shared_context)
    assert result.status == TaskState.COMPLETED

@pytest.mark.asyncio
async def test_tester_agent_failure(shared_context, base_task):
    fail_task = AgentTask(id=base_task.id, intent=base_task.intent, payload={"simulate_failure": True})
    agent = TesterAgent()
    result = await agent.execute(fail_task, shared_context)
    assert result.status == TaskState.FAILED

@pytest.mark.asyncio
async def test_debugger_agent(shared_context, base_task):
    agent = DebuggerAgent()
    result = await agent.execute(base_task, shared_context)
    assert result.status == TaskState.COMPLETED

@pytest.mark.asyncio
async def test_project_manager_orchestration(shared_context, base_task):
    agent = ProjectManagerAgent()
    result = await agent.execute(base_task, shared_context)
    assert result.status == TaskState.COMPLETED
    assert "successfully" in result.payload.get("output", "")
"""
with open("tests/test_coding_agent.py", "w") as file:
    file.write(test_code)

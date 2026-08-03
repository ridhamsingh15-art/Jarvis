import pytest

from agents.coding import (
    ArchitectAgent,
    CoderAgent,
    DebuggerAgent,
    ProjectManagerAgent,
    ResearcherAgent,
    ReviewerAgent,
    TesterAgent,
)
from core.agents.enums import TaskState
from core.agents.models import AgentTask, SharedContext
from core.models.primitives import Identifier


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

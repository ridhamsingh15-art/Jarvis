"""
Tests for the ContextOrchestrator.

Updated to use the new deterministic intent-based provider selection
(no LLM call needed to decide which providers to activate).
"""
import pytest
from unittest.mock import MagicMock
from core.cognition.context_orchestrator import ContextOrchestrator
from core.cognition.context_models import ProviderType, ContextChunk
from core.cognition.context import ShortTermContext
from core.cognition.retrieval import RetrievedMemory


def test_context_orchestrator():
    """Mission intent includes workspace and memory providers."""
    # Workspace provider returns a workspace chunk
    mock_workspace = MagicMock()
    mock_workspace.gather.return_value = [
        ContextChunk(
            content="Workspace Data",
            provider=ProviderType.WORKSPACE,
            relevance_score=1.0,
            recency_score=1.0,
            importance_score=1.0,
        )
    ]

    mock_mission = MagicMock()
    mock_mission.gather.return_value = []
    mock_project = MagicMock()
    mock_project.gather.return_value = []
    mock_tool = MagicMock()
    mock_tool.gather.return_value = []

    mock_retriever = MagicMock()
    mock_retriever.retrieve.return_value = [
        RetrievedMemory(content="Fact 1", source="sqlite_facts", relevance_score=0.9, memory_type="FACT")
    ]

    orchestrator = ContextOrchestrator(
        workspace_provider=mock_workspace,
        mission_provider=mock_mission,
        project_provider=mock_project,
        tool_provider=mock_tool,
        memory_retriever=mock_retriever,
    )

    ctx = ShortTermContext()
    ctx.add_message("user", "Hello")

    # Use mission intent — this includes MEMORY, PKI, WORKSPACE, PROJECT, MISSION, TOOL, CONVERSATION
    package = orchestrator.build("test input", ctx, intent="mission")

    # Workspace data should be included since MISSION intent selects WORKSPACE provider
    assert "Workspace Data" in package.workspace_state
    # Memory fact should be included since MISSION intent selects MEMORY provider
    assert "Fact 1" in package.memory_facts
    # Conversation is always included
    assert any("user: Hello" in c for c in package.recent_conversation)


def test_context_orchestrator_chat_excludes_memory():
    """CHAT intent must NOT trigger memory retrieval."""
    mock_retriever = MagicMock()
    mock_retriever.retrieve.return_value = []

    orchestrator = ContextOrchestrator(
        workspace_provider=MagicMock(gather=MagicMock(return_value=[])),
        mission_provider=MagicMock(gather=MagicMock(return_value=[])),
        project_provider=MagicMock(gather=MagicMock(return_value=[])),
        tool_provider=MagicMock(gather=MagicMock(return_value=[])),
        memory_retriever=mock_retriever,
    )

    ctx = ShortTermContext()
    ctx.add_message("user", "Hello")

    package = orchestrator.build("Hello", ctx, intent="chat")

    # Memory retriever must NOT have been called for a pure CHAT
    mock_retriever.retrieve.assert_not_called()


def test_context_orchestrator_no_llm_client_needed():
    """ContextOrchestrator must not require an LLM client for provider selection."""
    orchestrator = ContextOrchestrator(
        workspace_provider=MagicMock(gather=MagicMock(return_value=[])),
        mission_provider=MagicMock(gather=MagicMock(return_value=[])),
        project_provider=MagicMock(gather=MagicMock(return_value=[])),
        tool_provider=MagicMock(gather=MagicMock(return_value=[])),
        memory_retriever=MagicMock(retrieve=MagicMock(return_value=[])),
        # No llm_client passed — must still work
    )
    ctx = ShortTermContext()
    from core.cognition.context_models import ContextPackage
    result = orchestrator.build("Hi", ctx, intent="chat")
    assert isinstance(result, ContextPackage)

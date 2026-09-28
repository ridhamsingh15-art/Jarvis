import pytest
from unittest.mock import MagicMock, patch

from core.cognition.memory_orchestrator import MemoryOrchestrator
from core.cognition.retrieval import MemoryRetriever
from core.cognition.ranking import MemoryRanker
from core.cognition.summarizer import MemorySummarizer
from core.cognition.injector import ContextInjector
from core.cognition.models import RetrievedMemory, CognitiveContext, MemoryType
from core.cognition.context import ShortTermContext
from core.cognition.reflection import CognitiveReflection

@pytest.fixture
def mock_llm_client():
    client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = '["user name", "favourite IDE"]'
    client.generate.return_value = mock_response
    return client

@pytest.fixture
def mock_memory_manager():
    manager = MagicMock()
    manager._memory.search.return_value = []
    manager._memory.get_all_facts.return_value = {"user_name": "Ridham Singh"}
    return manager

@pytest.fixture
def mock_knowledge_manager():
    manager = MagicMock()
    manager.search.return_value = []
    return manager

def test_memory_retrieval(mock_llm_client, mock_memory_manager, mock_knowledge_manager):
    retriever = MemoryRetriever(mock_llm_client, mock_memory_manager, mock_knowledge_manager)
    results = retriever.retrieve("What is my name?")
    
    assert len(results) >= 1
    assert any(r.source == "sqlite_facts" for r in results)

def test_memory_ranking():
    ranker = MemoryRanker()
    memories = [
        RetrievedMemory(content="Fact 1", source="sqlite", relevance_score=0.5),
        RetrievedMemory(content="Fact 2", source="sqlite", relevance_score=0.9),
        RetrievedMemory(content="Fact 1", source="sqlite", relevance_score=0.1), # Duplicate lower score
    ]
    ranked = ranker.rank(memories, "test", max_items=2)
    
    assert len(ranked) == 2
    assert ranked[0].content == "Fact 2" # Highest score first
    assert ranked[1].content == "Fact 1" # Deduplicated

def test_memory_summarization():
    summarizer = MemorySummarizer()
    memories = [
        RetrievedMemory(content="Fact 1", source="sqlite_facts", memory_type=MemoryType.FACT),
        RetrievedMemory(content="Context 1", source="sqlite_history", memory_type=MemoryType.CONTEXT),
        RetrievedMemory(content="PKI 1", source="pki", memory_type=MemoryType.FACT),
    ]
    context = summarizer.summarize(memories)
    
    assert len(context.user_facts) == 1
    assert len(context.recent_context) == 1
    assert len(context.pki_results) == 1

def test_context_injector():
    injector = ContextInjector()
    context = CognitiveContext(
        user_facts=["Name: Ridham"],
        recent_context=["Asked for help"],
        pki_results=["Doc 1"]
    )
    result = injector.inject(context)
    
    assert "# Relevant User Facts" in result
    assert "- Name: Ridham" in result
    assert "# Recent Context" in result
    assert "- Asked for help" in result
    assert "# PKI Results" in result
    assert "- Doc 1" in result

def test_reflection(mock_llm_client, mock_memory_manager):
    reflection = CognitiveReflection(MagicMock(), mock_llm_client, mock_memory_manager)
    
    mock_response = MagicMock()
    mock_response.text = '{"should_remember": true, "facts_to_store": {"favourite_ide": "VS Code"}}'
    mock_llm_client.generate.return_value = mock_response
    
    reflection.reflect_on_conversation("My favourite IDE is VS Code.", "Got it!")
    
    mock_memory_manager.remember_fact.assert_called_with("favourite_ide", "VS Code")

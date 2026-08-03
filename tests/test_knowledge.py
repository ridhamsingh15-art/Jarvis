import os
import tempfile
from unittest.mock import MagicMock

import pytest

from core.events.bus import EventBus
from core.runtime.enums import ComponentState
from knowledge import (
    BinaryParserMock,
    DefaultHybridRetriever,
    DirectoryIndexer,
    IngestionPipeline,
    InMemoryKnowledgeRepository,
    InMemoryVectorStore,
    KnowledgeManager,
    KnowledgeQuery,
    MockEmbeddingProvider,
    MockReranker,
    RecursiveCharacterChunker,
    TextParser,
)


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as td:
        yield td

@pytest.fixture
def mock_files(temp_dir):
    txt_path = os.path.join(temp_dir, "test1.txt")
    with open(txt_path, "w") as f:
        f.write("This is a mock text file. Artificial Intelligence is great.")
        
    pdf_path = os.path.join(temp_dir, "test2.pdf")
    with open(pdf_path, "wb") as f:
        f.write(b"mock pdf content")
        
    return temp_dir, txt_path, pdf_path

@pytest.fixture
def manager():
    logger = MagicMock()
    event_bus = EventBus(logger)
    
    parsers = [TextParser(), BinaryParserMock()]
    chunker = RecursiveCharacterChunker(chunk_size=50, chunk_overlap=10)
    embedding = MockEmbeddingProvider()
    vector_store = InMemoryVectorStore()
    repository = InMemoryKnowledgeRepository()
    
    indexer = DirectoryIndexer(parsers)
    ingestion = IngestionPipeline(parsers, chunker, embedding, vector_store, repository)
    reranker = MockReranker()
    retriever = DefaultHybridRetriever(vector_store, embedding, reranker)
    
    return KnowledgeManager(
        indexer=indexer,
        ingestion_pipeline=ingestion,
        retriever=retriever,
        event_bus=event_bus,
        logger=logger
    )

@pytest.mark.asyncio
async def test_manager_lifecycle(manager):
    assert manager.state == ComponentState.INITIALIZED
    await manager.start()
    assert manager.state == ComponentState.RUNNING
    await manager.stop()
    assert manager.state == ComponentState.STOPPED

def test_index_file_and_search(manager, mock_files):
    _, txt_path, _ = mock_files
    
    doc_id = manager.index_file(txt_path)
    assert doc_id is not None
    
    # Try indexing again (duplicate detection should return same ID without re-indexing)
    doc_id_2 = manager.index_file(txt_path)
    assert doc_id == doc_id_2
    
    query = KnowledgeQuery(query_text="Artificial Intelligence", top_k=2)
    results = manager.search(query)
    
    assert len(results) > 0
    assert "Artificial Intelligence" in results[0].chunk.content

def test_index_folder(manager, mock_files):
    folder_path, _, _ = mock_files
    
    doc_ids = manager.index_folder(folder_path)
    assert len(doc_ids) == 2
    
    query = KnowledgeQuery(query_text="mock extracted content", top_k=2)
    results = manager.search(query)
    
    assert len(results) > 0
    # Should find the binary mock text
    assert "Mock extracted content" in results[0].chunk.content

def test_ask(manager, mock_files):
    folder_path, _, _ = mock_files
    manager.index_folder(folder_path)
    
    answer = manager.ask("Artificial")
    assert "Artificial" in answer

def test_remove(manager, mock_files):
    _, txt_path, _ = mock_files
    
    doc_id = manager.index_file(txt_path)
    assert doc_id is not None
    
    results = manager.search(KnowledgeQuery(query_text="Artificial"))
    assert len(results) > 0
    
    manager.remove(doc_id)
    
    results2 = manager.search(KnowledgeQuery(query_text="Artificial"))
    assert len(results2) == 0

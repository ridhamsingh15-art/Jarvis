import math
import os
import tempfile
import uuid
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from core.knowledge.indexer.chunking import get_chunks
from core.knowledge.indexer.embeddings import EmbeddingsEngine
from core.knowledge.indexer.metadata import determine_file_type, extract_metadata
from core.knowledge.indexer.registry import (
    KnowledgeChunk,
    KnowledgeDocument,
    SQLiteKnowledgeRegistry,
)
from core.knowledge.indexer.scanner import KnowledgeScanner


@pytest.fixture
def temp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    try:
        os.remove(path)
    except PermissionError:
        pass


@pytest.fixture
def temp_workspace():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create some dummy files
        p = Path(tmpdir)
        (p / "test.txt").write_text("Hello world this is a test text.")
        (p / "data.csv").write_text("id,name\n1,alice")
        
        # Ignored dir
        node_modules = p / "node_modules"
        node_modules.mkdir()
        (node_modules / "test.js").write_text("console.log('test')")
        
        # Subdir
        subdir = p / "projects"
        subdir.mkdir()
        (subdir / "main.py").write_text("print('hello')")
        
        yield tmpdir


def test_sqlite_registry_lifecycle(temp_db):
    registry = SQLiteKnowledgeRegistry(temp_db)
    
    doc = KnowledgeDocument(
        id=str(uuid.uuid4()),
        path="/dummy/path.txt",
        filename="path.txt",
        extension=".txt",
        file_type="text",
        size_bytes=100,
        last_modified=12345.0,
        last_indexed=0.0,
        metadata={"author": "test"}
    )
    
    # Insert
    registry.upsert_document(doc)
    retrieved = registry.get_document_by_path("/dummy/path.txt")
    assert retrieved is not None
    assert retrieved.filename == "path.txt"
    assert retrieved.metadata["author"] == "test"
    
    # Update
    doc.size_bytes = 200
    registry.upsert_document(doc)
    retrieved2 = registry.get_document_by_path("/dummy/path.txt")
    assert retrieved2.size_bytes == 200
    
    # Save Chunks
    chunk1 = KnowledgeChunk(id=str(uuid.uuid4()), document_id=doc.id, text="chunk1", embedding=[0.1, 0.2])
    chunk2 = KnowledgeChunk(id=str(uuid.uuid4()), document_id=doc.id, text="chunk2", embedding=None)
    registry.save_chunks([chunk1, chunk2])
    
    # Get embeddings
    chunks_with_emb = registry.get_all_chunks_with_embeddings()
    assert len(chunks_with_emb) == 1
    assert chunks_with_emb[0][1].text == "chunk1"
    
    # Delete doc should cascade
    registry.delete_document(doc.id)
    assert registry.get_document_by_path("/dummy/path.txt") is None
    assert len(registry.get_all_chunks_with_embeddings()) == 0


def test_metadata_extraction(temp_workspace):
    file_path = str(Path(temp_workspace) / "test.txt")
    meta = extract_metadata(file_path)
    assert "created_time" in meta
    assert "permissions" in meta
    
    assert determine_file_type(".txt") == "text"
    assert determine_file_type(".py") == "code"
    assert determine_file_type(".pdf") == "pdf"


def test_scanner_ignores_directories(temp_workspace):
    scanner = KnowledgeScanner([temp_workspace])
    docs = list(scanner.scan())
    
    paths = [d.path for d in docs]
    assert any("test.txt" in p for p in paths)
    assert any("data.csv" in p for p in paths)
    assert any("main.py" in p for p in paths)
    assert not any("test.js" in p for p in paths)  # in node_modules


def test_chunking():
    doc = KnowledgeDocument(
        id=str(uuid.uuid4()),
        path="dummy.txt",
        filename="dummy.txt",
        extension=".txt",
        file_type="text",
        size_bytes=100,
        last_modified=0.0,
        last_indexed=0.0,
        metadata={}
    )
    
    # Test _split_text indirectly via get_chunks if we mocked _extract_text
    # We will just write a temporary file
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp:
        tmp.write(b"A" * 1500)
        tmp_path = tmp.name
        
    try:
        doc.path = tmp_path
        chunks = get_chunks(doc)
        # 1500 bytes -> 1000 size + overlap 200 -> 2 chunks
        assert len(chunks) == 2
        assert len(chunks[0].text) > 500
    finally:
        os.remove(tmp_path)


def test_embeddings_engine():
    mock_client = MagicMock()
    mock_client.get_embeddings.return_value = [1.0, 0.0]
    
    engine = EmbeddingsEngine(mock_client)
    
    # Vector math
    sim = engine.compute_similarity([1.0, 0.0], [1.0, 0.0])
    assert math.isclose(sim, 1.0)
    
    sim2 = engine.compute_similarity([1.0, 0.0], [0.0, 1.0])
    assert math.isclose(sim2, 0.0)
    
    # Search
    doc = KnowledgeDocument(
        id="d1", path="x", filename="x", extension="x", 
        file_type="x", size_bytes=1, last_modified=1, last_indexed=1, metadata={}
    )
    chunk = KnowledgeChunk(id="c1", document_id="d1", text="hello", embedding=[1.0, 0.0])
    
    results = engine.search("hello", [(doc, chunk)])
    assert len(results) == 1
    assert results[0].score == 1.0

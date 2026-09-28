"""
Knowledge registry for persisting metadata, chunks, and embeddings.
"""

import json
import logging
import sqlite3
import struct
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

@dataclass
class KnowledgeDocument:
    id: str
    path: str
    filename: str
    extension: str
    file_type: str
    size_bytes: int
    last_modified: float
    last_indexed: float
    metadata: dict[str, Any]

@dataclass
class KnowledgeChunk:
    id: str
    document_id: str
    text: str
    embedding: list[float] | None = None

@dataclass
class KnowledgeSearchResult:
    document: KnowledgeDocument
    chunk: KnowledgeChunk
    score: float


class SQLiteKnowledgeRegistry:
    """Stores documents and chunks using SQLite.
    Embeddings are serialized to raw bytes (floats).
    """

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        # Check_same_thread=False since this will be used by the background scheduler
        # and queried by the agent from different threads.
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY,
                    path TEXT UNIQUE,
                    filename TEXT,
                    extension TEXT,
                    file_type TEXT,
                    size_bytes INTEGER,
                    last_modified REAL,
                    last_indexed REAL,
                    metadata TEXT
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS chunks (
                    id TEXT PRIMARY KEY,
                    document_id TEXT,
                    text TEXT,
                    embedding BLOB,
                    FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE
                )
            """)
            
            conn.execute("CREATE INDEX IF NOT EXISTS idx_chunks_doc_id ON chunks(document_id)")
            conn.commit()

    def close(self) -> None:
        pass  # Connections are created per-call and closed via context manager

    def _serialize_embedding(self, embedding: list[float]) -> bytes:
        return struct.pack(f'{len(embedding)}f', *embedding)
        
    def _deserialize_embedding(self, blob: bytes) -> list[float]:
        num_floats = len(blob) // 4
        return list(struct.unpack(f'{num_floats}f', blob))

    def upsert_document(self, doc: KnowledgeDocument) -> None:
        """Insert or update a document record."""
        with self._get_conn() as conn:
            conn.execute("""
                INSERT INTO documents 
                (id, path, filename, extension, file_type, size_bytes, last_modified, last_indexed, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(path) DO UPDATE SET
                    filename=excluded.filename,
                    extension=excluded.extension,
                    file_type=excluded.file_type,
                    size_bytes=excluded.size_bytes,
                    last_modified=excluded.last_modified,
                    last_indexed=excluded.last_indexed,
                    metadata=excluded.metadata,
                    id=excluded.id
            """, (
                doc.id, doc.path, doc.filename, doc.extension, doc.file_type, 
                doc.size_bytes, doc.last_modified, doc.last_indexed, 
                json.dumps(doc.metadata)
            ))
            conn.commit()

    def get_document_by_path(self, path: str) -> KnowledgeDocument | None:
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM documents WHERE path = ?", (path,)).fetchone()
            if not row:
                return None
            return self._row_to_doc(row)
            
    def _row_to_doc(self, row: sqlite3.Row) -> KnowledgeDocument:
        return KnowledgeDocument(
            id=row["id"],
            path=row["path"],
            filename=row["filename"],
            extension=row["extension"],
            file_type=row["file_type"],
            size_bytes=row["size_bytes"],
            last_modified=row["last_modified"],
            last_indexed=row["last_indexed"],
            metadata=json.loads(row["metadata"]) if row["metadata"] else {}
        )

    def delete_document(self, document_id: str) -> None:
        """Delete a document and all associated chunks (via CASCADE)."""
        with self._get_conn() as conn:
            # First verify we are enabling foreign keys for the cascade
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("DELETE FROM documents WHERE id = ?", (document_id,))
            conn.commit()

    def save_chunks(self, chunks: list[KnowledgeChunk]) -> None:
        """Save text chunks with optional embeddings."""
        if not chunks:
            return
            
        with self._get_conn() as conn:
            # First clear existing chunks for this document
            document_id = chunks[0].document_id
            conn.execute("DELETE FROM chunks WHERE document_id = ?", (document_id,))
            
            for chunk in chunks:
                emb_blob = self._serialize_embedding(chunk.embedding) if chunk.embedding else None
                conn.execute("""
                    INSERT INTO chunks (id, document_id, text, embedding)
                    VALUES (?, ?, ?, ?)
                """, (chunk.id, chunk.document_id, chunk.text, emb_blob))
            
            conn.commit()

    def get_all_chunks_with_embeddings(self) -> list[tuple[KnowledgeDocument, KnowledgeChunk]]:
        """Retrieve all chunks that have embeddings for vector search."""
        results = []
        with self._get_conn() as conn:
            cursor = conn.execute("""
                SELECT d.id as d_id, d.path, d.filename, d.extension, d.file_type, 
                       d.size_bytes, d.last_modified, d.last_indexed, d.metadata,
                       c.id as c_id, c.text, c.embedding
                FROM chunks c
                JOIN documents d ON c.document_id = d.id
                WHERE c.embedding IS NOT NULL
            """)
            for row in cursor:
                doc = KnowledgeDocument(
                    id=row["d_id"], path=row["path"], filename=row["filename"],
                    extension=row["extension"], file_type=row["file_type"],
                    size_bytes=row["size_bytes"], last_modified=row["last_modified"],
                    last_indexed=row["last_indexed"],
                    metadata=json.loads(row["metadata"]) if row["metadata"] else {}
                )
                chunk = KnowledgeChunk(
                    id=row["c_id"], document_id=doc.id, text=row["text"],
                    embedding=self._deserialize_embedding(row["embedding"])
                )
                results.append((doc, chunk))
        return results

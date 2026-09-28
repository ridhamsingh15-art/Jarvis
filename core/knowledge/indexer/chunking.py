"""
Splits files into smaller text chunks for semantic indexing.
"""

import logging
import uuid
from pathlib import Path

from .registry import KnowledgeChunk, KnowledgeDocument

logger = logging.getLogger(__name__)

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200

def get_chunks(document: KnowledgeDocument) -> list[KnowledgeChunk]:
    """Reads a file and returns a list of chunks."""
    if document.file_type in {"image", "video", "audio", "unknown"}:
        # Only index the metadata / filename for these
        return [_create_metadata_chunk(document)]
        
    text = _extract_text(document.path)
    if not text:
        return [_create_metadata_chunk(document)]
        
    chunks = _split_text(text)
    if not chunks:
        return [_create_metadata_chunk(document)]
        
    return [
        KnowledgeChunk(
            id=str(uuid.uuid4()),
            document_id=document.id,
            text=f"[{document.filename}] {chunk}"
        )
        for chunk in chunks
    ]

def _create_metadata_chunk(document: KnowledgeDocument) -> KnowledgeChunk:
    """Creates a chunk that just describes the file."""
    desc = f"File: {document.filename}\nType: {document.file_type}\nPath: {document.path}"
    return KnowledgeChunk(
        id=str(uuid.uuid4()),
        document_id=document.id,
        text=desc
    )

def _extract_text(path_str: str) -> str:
    path = Path(path_str)
    ext = path.suffix.lower()
    
    # We attempt basic text extraction for known plain-text
    if ext in {".txt", ".md", ".csv", ".json", ".xml", ".log", ".yaml", ".yml", ".py", ".js", ".ts", ".html", ".css", ".c", ".cpp", ".rs", ".go", ".java"}:
        try:
            return path.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            logger.debug("Failed to read text from %s: %s", path_str, e)
            return ""
            
    # For PDF, DOCX, etc, we'd need external libraries. 
    # For now, we fallback to empty string (so it just gets a metadata chunk)
    # unless we want to try to `import pypdf` here.
    return ""

def _split_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Basic sliding window chunker over text."""
    if not text:
        return []
        
    chunks = []
    start = 0
    text_len = len(text)
    
    while start < text_len:
        end = start + chunk_size
        chunks.append(text[start:end])
        if end >= text_len:
            break
        start = end - overlap
        
    return chunks

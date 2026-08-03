import builtins
import uuid

from core.models.primitives import Identifier

from .interfaces import ITextChunker
from .models import DocumentChunk, KnowledgeDocument


class RecursiveCharacterChunker(ITextChunker):
    """Splits text into chunks respecting character limits and boundaries."""

    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200) -> None:
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap

    def chunk(self, document: KnowledgeDocument) -> builtins.list[DocumentChunk]:
        if not document.content:
            return []

        # Simplified chunking logic for mock/test boundaries
        chunks = []
        text = document.content
        start = 0
        
        while start < len(text):
            end = start + self._chunk_size
            end = min(len(text), end)
                
            chunk_content = text[start:end]
            
            chunks.append(DocumentChunk(
                id=Identifier(f"chunk_{uuid.uuid4().hex[:8]}"),
                document_id=document.id,
                content=chunk_content,
                start_index=start,
                end_index=end
            ))
            
            if end == len(text):
                break
                
            start = end - self._chunk_overlap

        return chunks

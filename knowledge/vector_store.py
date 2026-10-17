import builtins
import copy
import math
import threading

from core.models.primitives import Identifier

from .interfaces import IVectorStore
from .models import DocumentChunk


class InMemoryVectorStore(IVectorStore):
    """Simple thread-safe in-memory vector store using cosine similarity."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._chunks: builtins.list[DocumentChunk] = []
        self._embeddings: builtins.list[builtins.list[float]] = []

    def add(self, chunks: builtins.list[DocumentChunk], embeddings: builtins.list[builtins.list[float]]) -> None:
        if len(chunks) != len(embeddings):
            raise ValueError("Mismatched chunks and embeddings length.")
            
        with self._lock:
            for c, e in zip(chunks, embeddings):
                self._chunks.append(copy.deepcopy(c))
                self._embeddings.append(e)

    def search(self, query_embedding: builtins.list[float], top_k: int = 5) -> builtins.list[tuple[DocumentChunk, float]]:
        with self._lock:
            if not self._chunks:
                return []
                
            scored_results = []
            for chunk, emb in zip(self._chunks, self._embeddings):
                score = self._cosine_similarity(query_embedding, emb)
                scored_results.append((copy.deepcopy(chunk), score))
                
            scored_results.sort(key=lambda x: x[1], reverse=True)
            return scored_results[:top_k]

    def remove(self, document_id: Identifier) -> None:
        with self._lock:
            indices_to_remove = []
            for i, chunk in enumerate(self._chunks):
                if chunk.document_id == document_id:
                    indices_to_remove.append(i)
                    
            for i in reversed(indices_to_remove):
                self._chunks.pop(i)
                self._embeddings.pop(i)

    def _cosine_similarity(self, v1: builtins.list[float], v2: builtins.list[float]) -> float:
        if len(v1) != len(v2) or len(v1) == 0:
            return 0.0
            
        dot_product = sum(a * b for a, b in zip(v1, v2))
        norm_v1 = math.sqrt(sum(a * a for a in v1))
        norm_v2 = math.sqrt(sum(b * b for b in v2))
        
        if norm_v1 == 0 or norm_v2 == 0:
            return 0.0
            
        return dot_product / (norm_v1 * norm_v2)

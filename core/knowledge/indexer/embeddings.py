"""
Vector embedding generation and semantic similarity computing.
"""

import math

from core.llm import LLMClient

from .registry import KnowledgeChunk, KnowledgeDocument, KnowledgeSearchResult


class EmbeddingsEngine:
    """Handles generating embeddings and vector search logic."""
    
    def __init__(self, llm_client: LLMClient) -> None:
        self.llm_client = llm_client
        
    def embed_chunk(self, chunk: KnowledgeChunk) -> None:
        """Fetches and sets the embedding for a chunk in-place."""
        if not chunk.text.strip():
            chunk.embedding = None
            return
            
        try:
            chunk.embedding = self.llm_client.get_embeddings(chunk.text)
        except Exception:
            # Fallback gracefully
            chunk.embedding = None
            
    def embed_query(self, query: str) -> list[float]:
        """Gets the embedding for a search query."""
        if not query.strip():
            return []
        try:
            return self.llm_client.get_embeddings(query)
        except Exception:
            return []

    def compute_similarity(self, vec1: list[float], vec2: list[float]) -> float:
        """Computes cosine similarity between two vectors."""
        if not vec1 or not vec2 or len(vec1) != len(vec2):
            return -1.0
            
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = math.sqrt(sum(a * a for a in vec1))
        norm2 = math.sqrt(sum(b * b for b in vec2))
        
        if norm1 == 0.0 or norm2 == 0.0:
            return -1.0
            
        return dot_product / (norm1 * norm2)

    def search(
        self, 
        query: str, 
        corpus: list[tuple[KnowledgeDocument, KnowledgeChunk]], 
        limit: int = 5
    ) -> list[KnowledgeSearchResult]:
        """Perform a semantic search over a pre-loaded corpus."""
        query_vec = self.embed_query(query)
        if not query_vec:
            return []
            
        results: list[KnowledgeSearchResult] = []
        for doc, chunk in corpus:
            if not chunk.embedding:
                continue
                
            score = self.compute_similarity(query_vec, chunk.embedding)
            # Minimum similarity threshold to ignore garbage matches
            if score > 0.4:
                results.append(KnowledgeSearchResult(
                    document=doc,
                    chunk=chunk,
                    score=score
                ))
                
        # Sort descending by score
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:limit]

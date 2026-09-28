import builtins
import copy

from .interfaces import IReranker
from .models import SearchResult


class MockReranker(IReranker):
    """Reranks search results. Provides deterministic mock for tests."""

    def rerank(self, query: str, results: builtins.list[SearchResult]) -> builtins.list[SearchResult]:
        if not results:
            return []
            
        reranked = []
        query_words = set(query.lower().split())
        
        for res in results:
            chunk_words = set(res.chunk.content.lower().split())
            overlap = len(query_words.intersection(chunk_words))
            
            # Boost score based on simple keyword overlap
            boosted_score = res.score + (overlap * 0.1)
            
            reranked.append(SearchResult(
                chunk=copy.deepcopy(res.chunk),
                score=boosted_score,
                source_attribution=copy.deepcopy(res.source_attribution)
            ))
            
        reranked.sort(key=lambda x: x.score, reverse=True)
        return reranked

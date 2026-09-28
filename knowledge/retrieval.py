import builtins

from .interfaces import IEmbeddingProvider, IHybridRetriever, IReranker, IVectorStore
from .models import KnowledgeQuery, SearchResult


class DefaultHybridRetriever(IHybridRetriever):
    """Combines keyword and semantic search."""

    def __init__(
        self,
        vector_store: IVectorStore,
        embedding_provider: IEmbeddingProvider,
        reranker: IReranker
    ) -> None:
        self._vector_store = vector_store
        self._embedding_provider = embedding_provider
        self._reranker = reranker

    def retrieve(self, query: KnowledgeQuery) -> builtins.list[SearchResult]:
        # 1. Vector Search
        query_emb = self._embedding_provider.embed_query(query.query_text)
        vector_results = self._vector_store.search(query_emb, top_k=query.top_k * 2)
        
        results = []
        for chunk, score in vector_results:
            results.append(SearchResult(
                chunk=chunk,
                score=score,
                source_attribution={"method": "vector_search", "document_id": chunk.document_id.value}
            ))
            
        # Mock Keyword search could be added here and combined into `results`.
        # For this implementation, we just use the vector results.
        
        # 2. Rerank
        final_results = self._reranker.rerank(query.query_text, results)
        
        return final_results[:query.top_k]

import builtins
from abc import ABC, abstractmethod

from core.models.primitives import Identifier

from .models import DocumentChunk, KnowledgeDocument, KnowledgeQuery, SearchResult


class IDocumentParser(ABC):
    @abstractmethod
    def parse(self, file_path: str) -> KnowledgeDocument:
        pass
        
    @abstractmethod
    def supports(self, file_path: str) -> bool:
        pass

class ITextChunker(ABC):
    @abstractmethod
    def chunk(self, document: KnowledgeDocument) -> builtins.list[DocumentChunk]:
        pass

class IEmbeddingProvider(ABC):
    @abstractmethod
    def embed_query(self, text: str) -> builtins.list[float]:
        pass
        
    @abstractmethod
    def embed_documents(self, texts: builtins.list[str]) -> builtins.list[builtins.list[float]]:
        pass

class IVectorStore(ABC):
    @abstractmethod
    def add(self, chunks: builtins.list[DocumentChunk], embeddings: builtins.list[builtins.list[float]]) -> None:
        pass
        
    @abstractmethod
    def search(self, query_embedding: builtins.list[float], top_k: int = 5) -> builtins.list[tuple[DocumentChunk, float]]:
        pass

    @abstractmethod
    def remove(self, document_id: Identifier) -> None:
        pass

class IHybridRetriever(ABC):
    @abstractmethod
    def retrieve(self, query: KnowledgeQuery) -> builtins.list[SearchResult]:
        pass

class IReranker(ABC):
    @abstractmethod
    def rerank(self, query: str, results: builtins.list[SearchResult]) -> builtins.list[SearchResult]:
        pass

class IKnowledgeRepository(ABC):
    @abstractmethod
    def save_document(self, document: KnowledgeDocument) -> None:
        pass

    @abstractmethod
    def get_document_by_hash(self, content_hash: str) -> KnowledgeDocument | None:
        pass

    @abstractmethod
    def remove_document(self, document_id: Identifier) -> None:
        pass

class IIndexer(ABC):
    @abstractmethod
    def index_folder(self, folder_path: str) -> builtins.list[Identifier]:
        pass
        
    @abstractmethod
    def index_file(self, file_path: str) -> Identifier | None:
        pass

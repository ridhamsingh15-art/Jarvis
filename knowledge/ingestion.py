import builtins
import logging

from core.models.primitives import Identifier

from .interfaces import (
    IDocumentParser,
    IEmbeddingProvider,
    IKnowledgeRepository,
    ITextChunker,
    IVectorStore,
)


class IngestionPipeline:
    """Orchestrates the flow: File -> Parser -> Chunker -> Embedding -> VectorStore."""

    def __init__(
        self,
        parsers: builtins.list[IDocumentParser],
        chunker: ITextChunker,
        embedding_provider: IEmbeddingProvider,
        vector_store: IVectorStore,
        repository: IKnowledgeRepository
    ) -> None:
        self._parsers = parsers
        self._chunker = chunker
        self._embedding_provider = embedding_provider
        self._vector_store = vector_store
        self._repository = repository
        self._logger = logging.getLogger(__name__)

    def ingest(self, file_path: str) -> Identifier | None:
        parser = self._get_parser(file_path)
        if not parser:
            self._logger.warning(f"No parser found for file: {file_path}")
            return None

        # 1. Parse
        document = parser.parse(file_path)

        # 2. Duplicate Detection
        existing_doc = self._repository.get_document_by_hash(document.content_hash)
        if existing_doc:
            self._logger.info(f"Document {file_path} already indexed. Skipping.")
            return existing_doc.id

        # 3. Save metadata
        self._repository.save_document(document)

        # 4. Chunk
        chunks = self._chunker.chunk(document)
        if not chunks:
            return document.id

        # 5. Embed
        chunk_texts = [c.content for c in chunks]
        embeddings = self._embedding_provider.embed_documents(chunk_texts)

        # 6. Store
        self._vector_store.add(chunks, embeddings)

        return document.id

    def remove(self, document_id: Identifier) -> None:
        self._repository.remove_document(document_id)
        self._vector_store.remove(document_id)

    def _get_parser(self, file_path: str) -> IDocumentParser | None:
        for parser in self._parsers:
            if parser.supports(file_path):
                return parser
        return None

import copy
import threading

from core.models.primitives import Identifier

from .interfaces import IKnowledgeRepository
from .models import KnowledgeDocument


class InMemoryKnowledgeRepository(IKnowledgeRepository):
    """Thread-safe persistence layer mapping document metadata."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._documents: dict[str, KnowledgeDocument] = {}

    def save_document(self, document: KnowledgeDocument) -> None:
        with self._lock:
            self._documents[document.id.value] = copy.deepcopy(document)

    def get_document_by_hash(self, content_hash: str) -> KnowledgeDocument | None:
        with self._lock:
            for doc in self._documents.values():
                if doc.content_hash == content_hash:
                    return copy.deepcopy(doc)
            return None

    def remove_document(self, document_id: Identifier) -> None:
        with self._lock:
            if document_id.value in self._documents:
                del self._documents[document_id.value]

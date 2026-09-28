from dataclasses import dataclass, field
from typing import Any

from core.models import JarvisModel
from core.models.primitives import Identifier, Timestamp


@dataclass(frozen=True, slots=True)
class KnowledgeDocument(JarvisModel):
    """Represents a parsed file containing raw text and metadata."""
    id: Identifier
    path: str
    content: str
    content_hash: str
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: Timestamp = field(default_factory=Timestamp)

@dataclass(frozen=True, slots=True)
class DocumentChunk(JarvisModel):
    """A specific portion of a document."""
    id: Identifier
    document_id: Identifier
    content: str
    start_index: int
    end_index: int
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True, slots=True)
class SearchResult(JarvisModel):
    """Output of a search query."""
    chunk: DocumentChunk
    score: float
    source_attribution: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True, slots=True)
class KnowledgeQuery(JarvisModel):
    """Encapsulates a search request."""
    query_text: str
    top_k: int = 5
    metadata_filters: dict[str, Any] = field(default_factory=dict)

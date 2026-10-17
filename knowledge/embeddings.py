import builtins
import hashlib

from .interfaces import IEmbeddingProvider


class MockEmbeddingProvider(IEmbeddingProvider):
    """Generates deterministic mock vector embeddings based on text hashes."""

    def __init__(self, dimension: int = 128) -> None:
        self._dimension = dimension

    def embed_query(self, text: str) -> builtins.list[float]:
        return self._generate_mock_vector(text)

    def embed_documents(self, texts: builtins.list[str]) -> builtins.list[builtins.list[float]]:
        return [self._generate_mock_vector(t) for t in texts]

    def _generate_mock_vector(self, text: str) -> builtins.list[float]:
        # Create a deterministic pseudo-random vector from the hash of the text
        h = hashlib.md5(text.encode("utf-8")).digest()
        
        vector = []
        for i in range(self._dimension):
            # Normalize byte value to [-1, 1] range
            val = (h[i % len(h)] / 255.0) * 2 - 1
            vector.append(val)
            
        return vector

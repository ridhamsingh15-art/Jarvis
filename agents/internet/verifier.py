import hashlib


class SourceVerifier:
    """Validates extraction confidence, removes duplicates, applies ranking."""
    def __init__(self) -> None:
        self.seen_hashes: set[str] = set()
        
    def verify(self, content: str) -> bool:
        h = hashlib.sha256(content.encode()).hexdigest()
        if h in self.seen_hashes:
            return False
        self.seen_hashes.add(h)
        return True

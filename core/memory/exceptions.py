from core.errors import JarvisError

class MemoryError(JarvisError):
    """Base exception for all memory subsystem failures."""
    pass

class MemoryNotFoundError(MemoryError):
    """Raised when a specific memory item cannot be located."""
    pass

class StorageProviderError(MemoryError):
    """Raised when the underlying persistence layer encounters an error."""
    pass

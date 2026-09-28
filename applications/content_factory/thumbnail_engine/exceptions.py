"""
Exceptions for the Thumbnail Engine.
"""
from core.errors import JarvisError

class ThumbnailEngineError(JarvisError):
    def __init__(self, message: str) -> None:
        super().__init__(message)

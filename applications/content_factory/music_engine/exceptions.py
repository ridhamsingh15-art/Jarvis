"""
Exceptions for the Music Engine.
"""

from core.errors import JarvisError

class MusicEngineError(JarvisError):
    def __init__(self, message: str) -> None:
        super().__init__(message)

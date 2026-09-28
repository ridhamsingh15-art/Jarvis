"""
Exceptions for the Subtitle Engine.
"""
from core.errors import JarvisError

class SubtitleEngineError(JarvisError):
    def __init__(self, message: str) -> None:
        super().__init__(message)

"""
Exceptions for the Publishing Engine.
"""
from core.errors import JarvisError

class PublishingEngineError(JarvisError):
    def __init__(self, message: str) -> None:
        super().__init__(message)

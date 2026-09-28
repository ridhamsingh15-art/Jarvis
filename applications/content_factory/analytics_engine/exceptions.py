"""
Exceptions for the Analytics Engine.
"""
from core.errors import JarvisError

class AnalyticsEngineError(JarvisError):
    def __init__(self, message: str) -> None:
        super().__init__(message)

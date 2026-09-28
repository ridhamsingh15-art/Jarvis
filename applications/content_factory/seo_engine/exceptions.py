"""
Exceptions for the SEO Engine.
"""
from core.errors import JarvisError

class SEOEngineError(JarvisError):
    def __init__(self, message: str) -> None:
        super().__init__(message)

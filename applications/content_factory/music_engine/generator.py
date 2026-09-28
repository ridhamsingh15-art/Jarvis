"""
Generator adapter for Music Engine.
"""

from .models import MusicGenerationRequest

class MusicGenerator:
    """Mock adapter for generating music (Suno/Local)."""
    
    def generate(self, request: MusicGenerationRequest) -> bytes:
        # Mock byte stream for generated audio
        return b"MOCK_MUSIC_DATA"

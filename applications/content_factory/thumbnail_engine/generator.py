"""
Generator adapter for Thumbnail Engine.
"""
from .models import ThumbnailGenerationRequest

class ThumbnailGenerator:
    """Mock generator for creating click-optimized thumbnails with overlays."""
    
    def generate(self, request: ThumbnailGenerationRequest) -> bytes:
        # Returns a mock byte stream simulating an overlaid image
        return b"MOCK_THUMBNAIL_DATA_WITH_OVERLAYS"

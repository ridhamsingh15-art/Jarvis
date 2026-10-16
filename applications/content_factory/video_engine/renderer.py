"""
Renderer for the Video Engine.
"""

from .ffmpeg_adapter import FFmpegAdapter
from .models import VideoTask


class VideoRenderer:
    """Orchestrates the rendering of the final video asset."""
    
    def __init__(self, adapter: FFmpegAdapter) -> None:
        self._adapter = adapter
        
    def render(self, task: VideoTask) -> bytes:
        """
        Invokes the adapter to render the task into a byte stream.
        """
        return self._adapter.render(task)

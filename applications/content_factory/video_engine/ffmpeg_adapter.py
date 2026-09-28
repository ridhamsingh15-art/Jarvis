"""
Adapter for FFmpeg interactions.
"""

from .models import VideoTask
from .exceptions import FFmpegError


class FFmpegAdapter:
    """Isolates subprocess calls to ffmpeg."""
    
    def render(self, task: VideoTask) -> bytes:
        """
        In a production environment, this would build the complex ffmpeg filter_complex
        string and invoke the subprocess. For this mock implementation, we validate
        the task and return a mock video payload.
        """
        if not task.clips:
            raise FFmpegError("Cannot render video without clips.")
            
        for clip in task.clips:
            if not clip.video_path:
                raise FFmpegError(f"Missing video path for scene {clip.scene_number}")
                
        # Mocking generation
        return b"MOCK_RENDERED_VIDEO_DATA"

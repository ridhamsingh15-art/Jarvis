"""
Data models for the Video Engine.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional


@dataclass
class TransitionConfig:
    """Configuration for a transition between clips."""
    transition_type: str = "cut"  # cut, crossfade, fade_to_black
    duration_seconds: float = 0.0


@dataclass
class TimelineClip:
    """Represents a single media clip in the assembly timeline."""
    scene_number: int
    video_path: str
    audio_path: Optional[str] = None
    start_time: float = 0.0
    duration: float = 0.0
    transition_out: TransitionConfig = field(default_factory=TransitionConfig)


@dataclass
class VideoParameters:
    """Parameters for final video rendering."""
    resolution: str = "1920x1080"
    fps: int = 24
    codec: str = "libx264"
    bitrate: str = "5M"


@dataclass
class VideoTask:
    """A task representing a single video assembly request."""
    task_id: str
    clips: List[TimelineClip]
    parameters: VideoParameters
    background_audio_path: Optional[str] = None
    subtitle_path: Optional[str] = None


@dataclass
class VideoMetadata:
    """Metadata for a successfully generated video asset."""
    resolution: str
    fps: int
    codec: str
    bitrate: str
    duration_seconds: float
    generation_parameters: Dict[str, Any]
    version: int
    timestamp: str


@dataclass
class VideoAsset:
    """Represents a final assembled video inside a Project Bundle."""
    filepath: str
    metadata: VideoMetadata

"""
Data models for the Voice Engine.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional

from core.models import Metadata


@dataclass
class VoiceParameters:
    """Parameters for driving the voice generation."""
    text: str
    speaker: str = "default_speaker"
    language: str = "en"
    speed: float = 1.0
    emotion: str = "neutral"
    voice_id: str = ""
    is_narration: bool = False
    
    
@dataclass
class VoiceTask:
    """A task representing a single audio clip generation request."""
    task_id: str
    scene_number: int
    model_name: str
    parameters: VoiceParameters


@dataclass
class VoiceMetadata:
    """Metadata for a successfully generated voice clip."""
    scene_number: int
    duration_seconds: float
    model_name: str
    speaker: str
    language: str
    speed: float
    emotion: str
    text: str
    voice_id: str
    is_narration: bool
    generation_parameters: Dict[str, Any]
    version: int
    timestamp: str


@dataclass
class VoiceAsset:
    """Represents a generated voice clip inside a Project Bundle."""
    filepath: str
    metadata: VoiceMetadata

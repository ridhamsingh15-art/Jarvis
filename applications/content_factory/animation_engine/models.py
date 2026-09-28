"""
Data models for the Animation Engine.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional

from core.models import Metadata


@dataclass
class AnimationParameters:
    """Parameters for driving the animation generation."""
    motion_prompt: str
    camera_motion: str
    negative_prompt: str = ""
    duration_seconds: int = 5
    fps: int = 24
    base_image_path: str = ""
    seed: int = -1
    cfg: float = 7.0


@dataclass
class AnimationTask:
    """A task representing a single clip generation request."""
    task_id: str
    scene_number: int
    model_name: str
    parameters: AnimationParameters


@dataclass
class AnimationMetadata:
    """Metadata for a successfully generated animation."""
    scene_number: int
    duration_seconds: int
    fps: int
    model_name: str
    motion_prompt: str
    camera_motion: str
    generation_parameters: Dict[str, Any]
    version: int
    timestamp: str


@dataclass
class AnimationAsset:
    """Represents a generated animation clip inside a Project Bundle."""
    filepath: str
    metadata: AnimationMetadata

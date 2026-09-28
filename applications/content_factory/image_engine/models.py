"""
Data models for the Image Generation Engine.
"""

from dataclasses import dataclass
from typing import Any

from core.models import JarvisModel


@dataclass(frozen=True, slots=True)
class GenerationParameters(JarvisModel):
    """Parameters passed to an Image Generation model adapter."""
    prompt: str
    negative_prompt: str = ""
    seed: int = -1
    cfg: float = 7.0
    steps: int = 30
    sampler: str = "euler_a"
    width: int = 1920
    height: int = 1080
    batch_size: int = 1


@dataclass(frozen=True, slots=True)
class ImageMetadata(JarvisModel):
    """Metadata sidecar saved alongside the physical image file."""
    prompt: str
    negative_prompt: str
    generation_model: str
    generation_parameters: dict[str, Any]
    seed: int
    sampler: str
    resolution: str
    generation_time: float
    scene_number: int
    version: int


@dataclass(frozen=True, slots=True)
class GenerationTask(JarvisModel):
    """A unit of work queued for the renderer."""
    project_id: str
    scene_number: int
    model_name: str
    parameters: GenerationParameters
    retry_count: int = 0

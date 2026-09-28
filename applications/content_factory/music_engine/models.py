"""
Models for the Music Engine.
"""

from dataclasses import dataclass
from typing import Any, Dict

@dataclass
class MusicGenerationRequest:
    prompt: str
    duration_seconds: float
    mood: str
    
@dataclass
class MusicAssetMetadata:
    duration: float
    prompt: str
    model: str

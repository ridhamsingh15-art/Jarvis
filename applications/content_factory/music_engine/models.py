"""
Models for the Music Engine.
"""

from dataclasses import dataclass


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

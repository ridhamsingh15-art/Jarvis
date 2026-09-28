"""
Models for the Subtitle Engine.
"""
from dataclasses import dataclass

@dataclass
class SubtitleGenerationRequest:
    text: str
    start_time: float
    end_time: float
    speaker: str
    
@dataclass
class SubtitleAssetMetadata:
    format: str
    total_segments: int

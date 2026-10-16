"""
Models for the Thumbnail Engine.
"""
from dataclasses import dataclass


@dataclass
class ThumbnailGenerationRequest:
    base_image_path: str
    title_text: str | None
    layout_style: str
    
@dataclass
class ThumbnailAssetMetadata:
    layout: str
    has_text: bool

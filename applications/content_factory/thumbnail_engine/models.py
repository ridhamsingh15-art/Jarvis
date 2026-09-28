"""
Models for the Thumbnail Engine.
"""
from dataclasses import dataclass
from typing import Optional

@dataclass
class ThumbnailGenerationRequest:
    base_image_path: str
    title_text: Optional[str]
    layout_style: str
    
@dataclass
class ThumbnailAssetMetadata:
    layout: str
    has_text: bool

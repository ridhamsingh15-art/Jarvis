"""
Models for the SEO Engine.
"""
from dataclasses import dataclass
from typing import List, Dict

@dataclass
class SEOAssetMetadata:
    title_length: int
    tags_count: int

"""
Models for the SEO Engine.
"""
from dataclasses import dataclass


@dataclass
class SEOAssetMetadata:
    title_length: int
    tags_count: int

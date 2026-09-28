"""
Data models for the Character & Asset Consistency Engine.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional


@dataclass
class CharacterProfile:
    """A consistent profile for a recurring character."""
    id: str
    name: str
    description: str
    role: str = ""
    reference_images: List[str] = field(default_factory=list)
    face_reference: str = ""
    clothing: str = ""
    accessories: str = ""
    color_palette: str = ""
    expressions: str = ""
    hair: str = ""
    body_type: str = ""
    age: str = ""
    species: str = ""
    style: str = ""
    personality_notes: str = ""


@dataclass
class EnvironmentProfile:
    """A consistent profile for a recurring environment/location."""
    id: str
    name: str
    description: str
    reference_images: List[str] = field(default_factory=list)
    architecture_style: str = ""
    lighting: str = ""
    weather: str = ""
    time_of_day: str = ""
    color_palette: str = ""
    props: str = ""


@dataclass
class ObjectProfile:
    """A consistent profile for a recurring prop/object."""
    id: str
    name: str
    description: str
    reference_images: List[str] = field(default_factory=list)
    material: str = ""
    color: str = ""
    scale: str = ""
    style: str = ""


@dataclass
class EnrichmentResult:
    """The result of enriching a prompt with consistency references."""
    original_prompt: str
    enriched_prompt: str
    matched_characters: List[str] = field(default_factory=list)
    matched_environments: List[str] = field(default_factory=list)
    matched_objects: List[str] = field(default_factory=list)

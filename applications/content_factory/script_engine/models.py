"""
Data models for the Script Engine.
"""

from dataclasses import dataclass, field

from core.models import JarvisModel


@dataclass(frozen=True, slots=True)
class ScriptScene(JarvisModel):
    """Represents a single scene in a generated script."""
    scene_number: int
    narration: str
    visual_description: str
    image_prompt: str
    animation_prompt: str
    sound_effects: str
    transition_notes: str


@dataclass(frozen=True, slots=True)
class ScriptSEO(JarvisModel):
    """SEO and packaging metadata for the script."""
    thumbnail_idea: str
    keywords: list[str]
    description_draft: str
    tags: list[str]


@dataclass(frozen=True, slots=True)
class ScriptPackage(JarvisModel):
    """The complete script package."""
    title: str
    summary: str
    target_audience: str
    estimated_duration: str
    voice_style: str
    music_suggestion: str
    scenes: list[ScriptScene] = field(default_factory=list)
    seo: ScriptSEO | None = None

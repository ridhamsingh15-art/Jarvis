"""
Data models for the Storyboard Engine.
"""

from dataclasses import dataclass, field

from core.models import JarvisModel


@dataclass(frozen=True, slots=True)
class StoryboardScene(JarvisModel):
    """Represents a fully fleshed out scene ready for visual production."""
    scene_number: int
    narration: str
    dialogue: str
    duration: float
    camera_angle: str
    camera_movement: str
    composition: str
    shot_type: str
    lighting: str
    time_of_day: str
    environment: str
    location: str
    characters: list[str]
    character_positions: str
    character_expressions: str
    character_motion: str
    props: list[str]
    background: str
    foreground: str
    color_palette: list[str]
    mood: str
    visual_style: str
    animation_notes: str
    transition: str
    sound_effects: str
    music_cue: str
    voice_timing: str
    
    # Base generic prompts
    image_prompt: str
    negative_prompt: str
    
    # Model-specific prompts (populated by adapters)
    comfyui_prompt: str = ""
    flux_prompt: str = ""
    wan_prompt: str = ""
    
    thumbnail_candidate: bool = False


@dataclass(frozen=True, slots=True)
class StoryboardPackage(JarvisModel):
    """The complete storyboard package wrapping the expanded script."""
    script_title: str
    visual_style_override: str
    scenes: list[StoryboardScene] = field(default_factory=list)

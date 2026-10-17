"""
Parses raw LLM dictionaries into StoryboardPackage models.
"""

from typing import Any

from .exceptions import StoryboardFormatError
from .models import StoryboardPackage, StoryboardScene


def format_storyboard(raw_data: dict[str, Any]) -> StoryboardPackage:
    """Transforms a raw JSON dictionary into a typed StoryboardPackage."""
    try:
        scenes = []
        for raw_scene in raw_data.get("scenes", []):
            scene = StoryboardScene(
                scene_number=int(raw_scene.get("scene_number", 0)),
                narration=str(raw_scene.get("narration", "")),
                dialogue=str(raw_scene.get("dialogue", "")),
                duration=float(raw_scene.get("duration", 0.0)),
                camera_angle=str(raw_scene.get("camera_angle", "")),
                camera_movement=str(raw_scene.get("camera_movement", "")),
                composition=str(raw_scene.get("composition", "")),
                shot_type=str(raw_scene.get("shot_type", "")),
                lighting=str(raw_scene.get("lighting", "")),
                time_of_day=str(raw_scene.get("time_of_day", "")),
                environment=str(raw_scene.get("environment", "")),
                location=str(raw_scene.get("location", "")),
                characters=[str(c) for c in raw_scene.get("characters", [])],
                character_positions=str(raw_scene.get("character_positions", "")),
                character_expressions=str(raw_scene.get("character_expressions", "")),
                character_motion=str(raw_scene.get("character_motion", "")),
                props=[str(p) for p in raw_scene.get("props", [])],
                background=str(raw_scene.get("background", "")),
                foreground=str(raw_scene.get("foreground", "")),
                color_palette=[str(c) for c in raw_scene.get("color_palette", [])],
                mood=str(raw_scene.get("mood", "")),
                visual_style=str(raw_scene.get("visual_style", "")),
                animation_notes=str(raw_scene.get("animation_notes", "")),
                transition=str(raw_scene.get("transition", "")),
                sound_effects=str(raw_scene.get("sound_effects", "")),
                music_cue=str(raw_scene.get("music_cue", "")),
                voice_timing=str(raw_scene.get("voice_timing", "")),
                image_prompt=str(raw_scene.get("image_prompt", "")),
                negative_prompt=str(raw_scene.get("negative_prompt", "")),
                comfyui_prompt=str(raw_scene.get("comfyui_prompt", "")),
                flux_prompt=str(raw_scene.get("flux_prompt", "")),
                wan_prompt=str(raw_scene.get("wan_prompt", "")),
                thumbnail_candidate=bool(raw_scene.get("thumbnail_candidate", False))
            )
            scenes.append(scene)

        return StoryboardPackage(
            script_title=str(raw_data.get("script_title", "Untitled Storyboard")),
            visual_style_override=str(raw_data.get("visual_style_override", "")),
            scenes=scenes
        )
    except (ValueError, TypeError) as e:
        raise StoryboardFormatError(f"Failed to map JSON values to StoryboardPackage fields: {e}") from e

"""
Parses raw dictionary representation into strictly typed ScriptPackage models.
"""

from typing import Any

from .exceptions import ScriptFormatError
from .models import ScriptPackage, ScriptScene, ScriptSEO


def format_script(raw_data: dict[str, Any]) -> ScriptPackage:
    """Transforms a raw JSON dictionary into a typed ScriptPackage."""
    try:
        scenes = []
        for raw_scene in raw_data.get("scenes", []):
            scene = ScriptScene(
                scene_number=int(raw_scene.get("scene_number", 0)),
                narration=str(raw_scene.get("narration", "")),
                visual_description=str(raw_scene.get("visual_description", "")),
                image_prompt=str(raw_scene.get("image_prompt", "")),
                animation_prompt=str(raw_scene.get("animation_prompt", "")),
                sound_effects=str(raw_scene.get("sound_effects", "")),
                transition_notes=str(raw_scene.get("transition_notes", ""))
            )
            scenes.append(scene)

        seo = None
        raw_seo = raw_data.get("seo")
        if raw_seo and isinstance(raw_seo, dict):
            seo = ScriptSEO(
                thumbnail_idea=str(raw_seo.get("thumbnail_idea", "")),
                keywords=[str(k) for k in raw_seo.get("keywords", [])],
                description_draft=str(raw_seo.get("description_draft", "")),
                tags=[str(t) for t in raw_seo.get("tags", [])]
            )

        return ScriptPackage(
            title=str(raw_data.get("title", "Untitled Script")),
            summary=str(raw_data.get("summary", "")),
            target_audience=str(raw_data.get("target_audience", "")),
            estimated_duration=str(raw_data.get("estimated_duration", "")),
            voice_style=str(raw_data.get("voice_style", "")),
            music_suggestion=str(raw_data.get("music_suggestion", "")),
            scenes=scenes,
            seo=seo
        )
    except (ValueError, TypeError) as e:
        raise ScriptFormatError(f"Failed to map JSON values to ScriptPackage fields: {e}") from e

"""
Timeline builder for the Video Engine.
"""

from typing import List, Dict

from applications.content_factory.project.models import ProjectBundle
from applications.content_factory.project.manager import ProjectManager
from applications.content_factory.storyboard_engine.models import StoryboardPackage
from .models import TimelineClip, TransitionConfig
from .transitions import TransitionBuilder
from .exceptions import TimelineError


class TimelineBuilder:
    """Builds the logical video timeline from the ProjectBundle."""
    
    def __init__(self, project_manager: ProjectManager) -> None:
        self._project_manager = project_manager

    def build(self, bundle: ProjectBundle) -> List[TimelineClip]:
        """
        Constructs a list of TimelineClips representing the final sequenced video.
        Uses the storyboard as the source of truth for scene ordering and transitions.
        """
        if not bundle.storyboard_package:
            raise TimelineError("ProjectBundle is missing a StoryboardPackage.")

        clips = []
        current_time = 0.0
        
        for scene in bundle.storyboard_package.scenes:
            # Locate animation asset
            animation_asset = None
            for asset in bundle.assets:
                if asset.metadata.asset_type == "animation" and getattr(asset, "scene_number", None) == scene.scene_number:
                    animation_asset = asset
                    break
                    
            if not animation_asset:
                raise TimelineError(f"Missing animation asset for scene {scene.scene_number}.")
                
            # Locate voice asset (optional)
            voice_asset = None
            for asset in bundle.assets:
                if asset.metadata.asset_type == "voice" and getattr(asset, "scene_number", None) == scene.scene_number:
                    voice_asset = asset
                    break
                    
            # Get physical paths
            storage = self._project_manager._storage
            video_path = storage.get_absolute_path(bundle.metadata.project_id, animation_asset.relative_path)
            audio_path = None
            if voice_asset:
                audio_path = storage.get_absolute_path(bundle.metadata.project_id, voice_asset.relative_path)
                
            # Build transition
            transition = TransitionBuilder.build_transition(scene.transition)
            
            # Duration fallback (ideally from metadata)
            duration = getattr(animation_asset.metadata, "duration_seconds", scene.duration)
            if duration <= 0:
                duration = 2.0
                
            clip = TimelineClip(
                scene_number=scene.scene_number,
                video_path=video_path,
                audio_path=audio_path,
                start_time=current_time,
                duration=duration,
                transition_out=transition
            )
            clips.append(clip)
            
            # Advance time (subtract transition duration for overlap if crossfade)
            current_time += duration
            if transition.transition_type == "crossfade":
                current_time -= transition.duration_seconds
                
        return clips

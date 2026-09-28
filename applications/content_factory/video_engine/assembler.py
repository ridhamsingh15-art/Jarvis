"""
Assembler for the Video Engine.
"""

from typing import List

from .models import TimelineClip, VideoTask, VideoParameters
from .timeline import TimelineBuilder
from applications.content_factory.project.models import ProjectBundle


class SceneSequencer:
    """High-level assembler connecting the timeline builder with rendering parameters."""
    
    def __init__(self, timeline_builder: TimelineBuilder) -> None:
        self._timeline_builder = timeline_builder

    def assemble(self, task_id: str, bundle: ProjectBundle, params: VideoParameters) -> VideoTask:
        """
        Takes the bundle, builds the timeline, and outputs a complete VideoTask
        that the renderer can execute.
        """
        clips = self._timeline_builder.build(bundle)
        
        background_audio_path = None
        subtitle_path = None
        
        storage = self._timeline_builder._project_manager._storage
        
        for asset in bundle.assets:
            if asset.metadata.asset_type == "music" and "background" in asset.tags:
                background_audio_path = storage.get_absolute_path(bundle.metadata.project_id, asset.relative_path)
            elif asset.metadata.asset_type == "subtitle":
                subtitle_path = storage.get_absolute_path(bundle.metadata.project_id, asset.relative_path)
        
        return VideoTask(
            task_id=task_id,
            clips=clips,
            parameters=params,
            background_audio_path=background_audio_path,
            subtitle_path=subtitle_path
        )

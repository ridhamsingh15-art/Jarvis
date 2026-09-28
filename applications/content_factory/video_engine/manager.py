"""
Capability Facade and Mission Control integration for the Video Engine.
"""

import logging
import threading

from applications.content_factory.project.manager import ProjectManager
from core.capability.models import Capability, CapabilityType
from core.mission.manager import MissionManager
from core.mission.models import Mission
from core.models import Metadata

from .planner import VideoGenerationPlanner
from .models import VideoParameters

logger = logging.getLogger(__name__)


class VideoEngineManager:
    """Public facade for the Video Engine."""

    def __init__(
        self,
        planner: VideoGenerationPlanner,
        mission_manager: MissionManager,
        project_manager: ProjectManager
    ) -> None:
        self._planner = planner
        self._mission_manager = mission_manager
        self._project_manager = project_manager

    def get_capability_metadata(self) -> Capability:
        return Capability(
            name="video_engine",
            description="Combines all generated media assets into a complete video timeline.",
            type=CapabilityType.AGENT
        )

    def generate_video_async(self, project_id: str, resolution: str = "1920x1080", fps: int = 24) -> str:
        """Triggers video assembly in the background and returns the Mission ID."""
        
        mission = Mission(
            title=f"Video Assembly: {project_id[:10]}",
            description=f"Rendering final video for project {project_id}.",
            priority=4,
            metadata=Metadata(annotations={"project_id": project_id})
        )
        mission = self._mission_manager.create(mission)
        self._mission_manager.queue(mission.mission_id.value)
        
        params = VideoParameters(resolution=resolution, fps=fps)
        
        thread = threading.Thread(
            target=self._run_and_monitor,
            args=(mission.mission_id.value, project_id, params),
            daemon=True
        )
        thread.start()
        
        return mission.mission_id.value

    def _run_and_monitor(self, mission_id: str, project_id: str, params: VideoParameters) -> None:
        """Background thread executing the generation and updating Mission status."""
        try:
            self._mission_manager.ready(mission_id)
            self._mission_manager.resume(mission_id)
            
            # Fetch the latest bundle
            bundle = self._project_manager.get_project(project_id)
            
            # Execute planner
            updated_bundle = self._planner.execute(bundle, params)
            
            # Mark bundle with the new mission
            from applications.content_factory.project.bundle import BundleModifier
            updated_bundle = BundleModifier.add_mission(updated_bundle, mission_id)
            self._project_manager.save_project(updated_bundle)
            
            self._mission_manager.complete(mission_id)
            
        except Exception as e:
            logger.error("Background video generation failed for mission %s: %s", mission_id, e)
            try:
                self._mission_manager.fail(mission_id)
            except Exception:
                pass

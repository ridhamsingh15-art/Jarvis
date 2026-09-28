"""
Manager for the Thumbnail Engine.
"""
import threading
from core.mission.manager import MissionManager
from core.mission.models import Mission
from core.models import Metadata
from core.capability.models import Capability, CapabilityType
from applications.content_factory.project.manager import ProjectManager

from .planner import ThumbnailGenerationPlanner

class ThumbnailEngineManager:
    def __init__(self, planner: ThumbnailGenerationPlanner, mission_manager: MissionManager, project_manager: ProjectManager):
        self._planner = planner
        self._mission_manager = mission_manager
        self._project_manager = project_manager

    def get_capability_metadata(self) -> Capability:
        return Capability(name="thumbnail_engine", description="Generates click-optimized thumbnails.", type=CapabilityType.AGENT)

    def generate_thumbnail_async(self, project_id: str) -> str:
        mission = self._mission_manager.create(Mission(
            title=f"Thumbnail Generation: {project_id[:10]}",
            description="Generating video thumbnail.",
            priority=4,
            metadata=Metadata(annotations={"project_id": project_id})
        ))
        self._mission_manager.queue(mission.mission_id.value)
        
        threading.Thread(target=self._run, args=(mission.mission_id.value, project_id), daemon=True).start()
        return mission.mission_id.value

    def _run(self, mission_id: str, project_id: str) -> None:
        try:
            self._mission_manager.ready(mission_id)
            self._mission_manager.resume(mission_id)
            
            bundle = self._project_manager.get_project(project_id)
            updated = self._planner.execute(bundle)
            
            from applications.content_factory.project.bundle import BundleModifier
            updated = BundleModifier.add_mission(updated, mission_id)
            self._project_manager.save_project(updated)
            
            self._mission_manager.complete(mission_id)
        except Exception:
            try:
                self._mission_manager.fail(mission_id)
            except Exception:
                pass

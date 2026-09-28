"""
Capability Facade and Mission Control integration for the Voice Engine.
"""

import logging
import threading

from applications.content_factory.project.manager import ProjectManager
from core.capability.models import Capability, CapabilityType
from core.mission.manager import MissionManager
from core.mission.models import Mission
from core.models import Metadata

from .planner import VoiceGenerationPlanner

logger = logging.getLogger(__name__)


class VoiceEngineManager:
    """Public facade for the Voice Engine."""

    def __init__(
        self,
        planner: VoiceGenerationPlanner,
        mission_manager: MissionManager,
        project_manager: ProjectManager
    ) -> None:
        self._planner = planner
        self._mission_manager = mission_manager
        self._project_manager = project_manager

    def get_capability_metadata(self) -> Capability:
        return Capability(
            name="voice_engine",
            description="Transforms narration and dialogue from the ScriptPackage into high-quality voice assets.",
            type=CapabilityType.AGENT
        )

    def generate_voice_async(self, project_id: str, model_name: str = "piper") -> str:
        """Triggers voice batch generation in the background and returns the Mission ID."""
        
        mission = Mission(
            title=f"Voice Generation: {project_id[:10]}",
            description=f"Rendering voiceover for project {project_id} using {model_name}.",
            priority=3,
            metadata=Metadata(annotations={"project_id": project_id, "model_name": model_name})
        )
        mission = self._mission_manager.create(mission)
        self._mission_manager.queue(mission.mission_id.value)
        
        thread = threading.Thread(
            target=self._run_and_monitor,
            args=(mission.mission_id.value, project_id, model_name),
            daemon=True
        )
        thread.start()
        
        return mission.mission_id.value

    def _run_and_monitor(self, mission_id: str, project_id: str, model_name: str) -> None:
        """Background thread executing the generation batch and updating Mission status."""
        try:
            self._mission_manager.ready(mission_id)
            self._mission_manager.resume(mission_id)
            
            # Fetch the latest bundle
            bundle = self._project_manager.get_project(project_id)
            
            # Execute planner
            updated_bundle = self._planner.execute_batch(bundle, model_name)
            
            # Mark bundle with the new mission
            from applications.content_factory.project.bundle import BundleModifier
            updated_bundle = BundleModifier.add_mission(updated_bundle, mission_id)
            self._project_manager.save_project(updated_bundle)
            
            self._mission_manager.complete(mission_id)
            
        except Exception as e:
            logger.error("Background voice generation failed for mission %s: %s", mission_id, e)
            try:
                self._mission_manager.fail(mission_id)
            except Exception:
                pass

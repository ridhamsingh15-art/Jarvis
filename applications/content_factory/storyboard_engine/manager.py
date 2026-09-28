"""
Capability Facade and Mission Control integration for the Storyboard Engine.
"""

import logging
import threading

from applications.content_factory.script_engine.models import ScriptPackage
from core.capability.models import Capability, CapabilityType
from core.mission.enums import MissionStatus
from core.mission.manager import MissionManager
from core.mission.models import Mission
from core.models import Metadata

from .planner import StoryboardPlanner

logger = logging.getLogger(__name__)


class StoryboardEngineManager:
    """Public facade for the Storyboard Generation Engine."""

    def __init__(
        self,
        planner: StoryboardPlanner,
        mission_manager: MissionManager
    ) -> None:
        self._planner = planner
        self._mission_manager = mission_manager

    def get_capability_metadata(self) -> Capability:
        """Returns the Capability model for router registration."""
        return Capability(
            name="storyboard_engine",
            description="Transforms a ScriptPackage into a complete production-ready StoryboardPackage.",
            type=CapabilityType.AGENT
        )

    def generate_storyboard_async(self, script: ScriptPackage, visual_style: str = "") -> str:
        """Triggers storyboard generation in the background and returns the Mission ID."""
        
        mission = Mission(
            title=f"Storyboard: {script.title[:30]}",
            description=f"Generating a storyboard for the script '{script.title}'.",
            priority=2,
            metadata=Metadata(annotations={"script_title": script.title, "style_override": visual_style})
        )
        mission = self._mission_manager.create(mission)
        self._mission_manager.queue(mission.mission_id.value)
        
        thread = threading.Thread(
            target=self._run_and_monitor,
            args=(mission.mission_id.value, script, visual_style),
            daemon=True
        )
        thread.start()
        
        return mission.mission_id.value

    def _run_and_monitor(self, mission_id: str, script: ScriptPackage, visual_style: str) -> None:
        """Background thread executing the storyboard plan and updating Mission status."""
        try:
            self._mission_manager.ready(mission_id)
            self._mission_manager.resume(mission_id)
            
            # Periodically check for cancellation during generation
            current_mission = self._mission_manager.get(mission_id)
            if current_mission.status == MissionStatus.CANCELLED:
                logger.info("Storyboard generation mission %s was cancelled.", mission_id)
                return

            # Execute
            package = self._planner.execute_plan(mission_id, script, visual_style)
            
            # Save the JSON dict representation to the mission metadata
            current_mission = self._mission_manager.get(mission_id)
            meta_data = dict(current_mission.metadata.annotations)
            import dataclasses
            meta_data["storyboard_package"] = dataclasses.asdict(package)
            self._mission_manager.update(mission_id, metadata=Metadata(annotations=meta_data))
            
            self._mission_manager.complete(mission_id)
            
        except Exception as e:
            logger.error("Background storyboard generation failed for mission %s: %s", mission_id, e)
            try:
                self._mission_manager.fail(mission_id)
            except Exception:
                pass

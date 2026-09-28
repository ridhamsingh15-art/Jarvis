"""
Capability Facade and Mission Control integration for the Script Engine.
"""

import logging
import threading

from core.capability.models import Capability, CapabilityType
from core.mission.enums import MissionStatus
from core.mission.manager import MissionManager
from core.mission.models import Mission
from core.models import Metadata

from .planner import ScriptPlanner

logger = logging.getLogger(__name__)


class ScriptEngineManager:
    """Public facade for the Script Generation Engine."""

    def __init__(
        self,
        planner: ScriptPlanner,
        mission_manager: MissionManager
    ) -> None:
        self._planner = planner
        self._mission_manager = mission_manager

    def get_capability_metadata(self) -> Capability:
        """Returns the Capability model for router registration."""
        return Capability(
            name="script_engine",
            description="Generates complete, production-ready video scripts and content templates.",
            type=CapabilityType.AGENT
        )

    def generate_script_async(self, topic: str, style: str, context: str = "") -> str:
        """Triggers script generation in the background and returns the Mission ID."""
        
        mission = Mission(
            title=f"Write Script: {topic[:30]}...",
            description=f"Generating a {style} script about {topic}.",
            priority=2,
            metadata=Metadata(annotations={"topic": topic, "style": style, "context": context})
        )
        mission = self._mission_manager.create(mission)
        self._mission_manager.queue(mission.mission_id.value)
        
        thread = threading.Thread(
            target=self._run_and_monitor,
            args=(mission.mission_id.value, topic, style, context),
            daemon=True
        )
        thread.start()
        
        return mission.mission_id.value

    def _run_and_monitor(self, mission_id: str, topic: str, style: str, context: str) -> None:
        """Background thread executing the script plan and updating Mission status."""
        try:
            self._mission_manager.ready(mission_id)
            self._mission_manager.resume(mission_id)
            
            # Periodically check for cancellation during long generation
            # (In a real async architecture we would pass a cancellation token)
            current_mission = self._mission_manager.get(mission_id)
            if current_mission.status == MissionStatus.CANCELLED:
                logger.info("Script generation mission %s was cancelled.", mission_id)
                return

            # Execute
            package = self._planner.execute_plan(mission_id, topic, style, context)
            
            # Save the JSON dict representation to the mission metadata so it can be extracted
            # by future systems (like N8n).
            current_mission = self._mission_manager.get(mission_id)
            meta_data = dict(current_mission.metadata.annotations)
            # Use __dict__ recursively or a dataclass serialization
            import dataclasses
            meta_data["script_package"] = dataclasses.asdict(package)
            self._mission_manager.update(mission_id, metadata=Metadata(annotations=meta_data))
            
            self._mission_manager.complete(mission_id)
            
        except Exception as e:
            logger.error("Background script generation failed for mission %s: %s", mission_id, e)
            try:
                self._mission_manager.fail(mission_id)
            except Exception:
                pass

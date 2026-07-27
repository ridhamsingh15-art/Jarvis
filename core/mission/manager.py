import time
from typing import List, Optional
from dataclasses import replace

from core.events import EventBus
from core.models import Event, Timestamp
from .enums import MissionStatus
from .models import Mission
from .interfaces import MissionRepository
from .exceptions import InvalidMissionTransitionError

class MissionManager:
    """Orchestrates Mission lifecycles and business rules."""
    
    # Pre-defined valid transitions
    VALID_TRANSITIONS = {
        MissionStatus.CREATED: {MissionStatus.QUEUED},
        MissionStatus.QUEUED: {MissionStatus.PLANNING, MissionStatus.CANCELLED},
        MissionStatus.PLANNING: {MissionStatus.READY, MissionStatus.FAILED, MissionStatus.CANCELLED},
        MissionStatus.READY: {MissionStatus.RUNNING, MissionStatus.CANCELLED},
        MissionStatus.RUNNING: {MissionStatus.PAUSED, MissionStatus.COMPLETED, MissionStatus.FAILED, MissionStatus.CANCELLED},
        MissionStatus.PAUSED: {MissionStatus.RUNNING, MissionStatus.CANCELLED},
        MissionStatus.COMPLETED: set(),
        MissionStatus.FAILED: set(),
        MissionStatus.CANCELLED: set()
    }
    
    def __init__(self, repository: MissionRepository, event_bus: EventBus):
        self._repository = repository
        self._event_bus = event_bus
        
    def _transition_status(self, mission: Mission, new_status: MissionStatus) -> Mission:
        """Validates and applies a status transition, publishing the event."""
        if new_status not in self.VALID_TRANSITIONS[mission.status]:
            raise InvalidMissionTransitionError(
                f"Cannot transition Mission from {mission.status.value} to {new_status.value}"
            )
            
        # Create an updated mission instance (since models are frozen)
        now = Timestamp()
        kwargs = {
            "status": new_status,
            "updated_at": now
        }
        
        # Auto-set specific timestamps based on status
        if new_status == MissionStatus.RUNNING and mission.started_at is None:
            kwargs["started_at"] = now
        elif new_status in (MissionStatus.COMPLETED, MissionStatus.FAILED, MissionStatus.CANCELLED):
            kwargs["completed_at"] = now
            
        updated = replace(mission, **kwargs)
        
        self._repository.save(updated)
        
        # Format the event topic. Examples:
        # MissionCreated, MissionStarted, MissionPaused, MissionCompleted, MissionCancelled, MissionFailed
        event_action = new_status.value.capitalize()
        topic = f"Mission{event_action}"
        
        self._event_bus.publish(Event(topic=topic, payload={"mission_id": updated.mission_id.value}))
        return updated

    def create(self, mission: Mission) -> Mission:
        """Saves a new mission and triggers MissionCreated."""
        self._repository.save(mission)
        self._event_bus.publish(Event(topic="MissionCreated", payload={"mission_id": mission.mission_id.value}))
        return mission
        
    def get(self, mission_id: str) -> Mission:
        return self._repository.get(mission_id)
        
    def list(self) -> List[Mission]:
        return self._repository.list()
        
    def update(self, mission_id: str, progress: Optional[float] = None, **kwargs) -> Mission:
        """Updates specific safe fields like progress."""
        mission = self.get(mission_id)
        
        updates = {"updated_at": Timestamp()}
        if progress is not None:
            if not (0.0 <= progress <= 100.0):
                raise ValueError("Progress must be between 0 and 100")
            updates["progress"] = progress
            
        # Optional metadata updates could be supported here
            
        updated = replace(mission, **updates)
        return self._repository.save(updated)
        
    # State transition wrappers
    def queue(self, mission_id: str) -> Mission:
        return self._transition_status(self.get(mission_id), MissionStatus.QUEUED)
        
    def plan(self, mission_id: str) -> Mission:
        return self._transition_status(self.get(mission_id), MissionStatus.PLANNING)
        
    def ready(self, mission_id: str) -> Mission:
        return self._transition_status(self.get(mission_id), MissionStatus.READY)
        
    def resume(self, mission_id: str) -> Mission:
        # Used for both READY -> RUNNING and PAUSED -> RUNNING
        return self._transition_status(self.get(mission_id), MissionStatus.RUNNING)
        
    def pause(self, mission_id: str) -> Mission:
        return self._transition_status(self.get(mission_id), MissionStatus.PAUSED)
        
    def cancel(self, mission_id: str) -> Mission:
        return self._transition_status(self.get(mission_id), MissionStatus.CANCELLED)
        
    def complete(self, mission_id: str) -> Mission:
        return self._transition_status(self.get(mission_id), MissionStatus.COMPLETED)
        
    def fail(self, mission_id: str) -> Mission:
        return self._transition_status(self.get(mission_id), MissionStatus.FAILED)
        
    def delete(self, mission_id: str) -> None:
        self._repository.delete(mission_id)
        
    def exists(self, mission_id: str) -> bool:
        return self._repository.exists(mission_id)

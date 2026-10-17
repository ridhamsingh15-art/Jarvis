from dataclasses import dataclass, field

from core.models import Identifier, JarvisModel, Metadata, Timestamp

from .enums import MissionPriority, MissionStatus


@dataclass(frozen=True, slots=True)
class Mission(JarvisModel):
    """
    Immutable representation of the highest-level unit of work.
    """
    mission_id: Identifier = field(default_factory=Identifier)
    title: str = "Unnamed Mission"
    description: str = ""
    priority: MissionPriority = MissionPriority.NORMAL
    status: MissionStatus = MissionStatus.CREATED
    
    created_at: Timestamp = field(default_factory=Timestamp)
    updated_at: Timestamp = field(default_factory=Timestamp)
    started_at: Timestamp | None = None
    completed_at: Timestamp | None = None
    
    progress: float = 0.0 # 0 to 100
    
    tags: list[str] = field(default_factory=list)
    metadata: Metadata = field(default_factory=Metadata)
    parent_mission_id: Identifier | None = None

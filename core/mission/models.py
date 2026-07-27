from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
import time

from core.models import Identifier, Timestamp, Metadata, JarvisModel
from .enums import MissionStatus, MissionPriority

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
    started_at: Optional[Timestamp] = None
    completed_at: Optional[Timestamp] = None
    
    progress: float = 0.0 # 0 to 100
    
    tags: List[str] = field(default_factory=list)
    metadata: Metadata = field(default_factory=Metadata)
    parent_mission_id: Optional[Identifier] = None

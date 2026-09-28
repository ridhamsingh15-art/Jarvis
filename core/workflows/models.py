from dataclasses import dataclass, field

from core.models import Identifier, JarvisModel, Metadata, Timestamp, Version

from .enums import WorkflowPriority, WorkflowStatus


@dataclass(frozen=True, slots=True)
class Workflow(JarvisModel):
    """
    Immutable representation of a Workflow inside a Mission.
    """
    workflow_id: Identifier = field(default_factory=Identifier)
    mission_id: Identifier = field(default_factory=Identifier)
    title: str = "Unnamed Workflow"
    description: str = ""
    status: WorkflowStatus = WorkflowStatus.CREATED
    priority: WorkflowPriority = WorkflowPriority.NORMAL
    
    created_at: Timestamp = field(default_factory=Timestamp)
    updated_at: Timestamp = field(default_factory=Timestamp)
    started_at: Timestamp | None = None
    completed_at: Timestamp | None = None
    
    progress: float = 0.0 # 0 to 100
    
    metadata: Metadata = field(default_factory=Metadata)
    tags: list[str] = field(default_factory=list)
    version: Version = field(default_factory=Version)

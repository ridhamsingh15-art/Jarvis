from dataclasses import dataclass, field
from typing import List, Optional

from core.models import Identifier, Timestamp, Metadata, Version, JarvisModel
from .enums import TaskStatus, TaskPriority

@dataclass(frozen=True, slots=True)
class Task(JarvisModel):
    """
    Immutable representation of a Task within a Workflow.
    """
    task_id: Identifier = field(default_factory=Identifier)
    workflow_id: Identifier = field(default_factory=Identifier)
    title: str = "Unnamed Task"
    description: str = ""
    status: TaskStatus = TaskStatus.CREATED
    priority: TaskPriority = TaskPriority.NORMAL
    
    created_at: Timestamp = field(default_factory=Timestamp)
    updated_at: Timestamp = field(default_factory=Timestamp)
    started_at: Optional[Timestamp] = None
    completed_at: Optional[Timestamp] = None
    
    progress: float = 0.0 # 0 to 100
    
    metadata: Metadata = field(default_factory=Metadata)
    tags: List[str] = field(default_factory=list)
    version: Version = field(default_factory=Version)
    
    # Execution configurations
    timeout_seconds: Optional[int] = None
    retry_count: int = 0
    max_retries: int = 0

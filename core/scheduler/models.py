import itertools
from dataclasses import dataclass, field
from typing import Dict, Any, Optional
import time

from core.models import JarvisModel, Identifier
from .enums import ScheduleStatus, JobType

_job_sequence = itertools.count()

@dataclass(frozen=True, slots=True)
class ScheduledJob(JarvisModel):
    """Immutable representation of a job waiting in the scheduler."""
    id: Identifier = field(default_factory=Identifier)
    job_type: JobType = JobType.TASK
    payload_id: Identifier = field(default_factory=Identifier)
    
    # Absolute timestamp (seconds since epoch) when this job should fire
    next_execution_time: float = 0.0
    
    status: ScheduleStatus = ScheduleStatus.PENDING
    
    # Store trigger metadata to compute recurring jobs
    trigger_type: str = "IMMEDIATE"
    trigger_metadata: Dict[str, Any] = field(default_factory=dict)
    
    created_at: float = field(default_factory=time.time)
    
    # Stable secondary key for deterministic heap ordering
    sequence_number: int = field(default_factory=lambda: next(_job_sequence))

    def __lt__(self, other: 'ScheduledJob') -> bool:
        """Min-heap ordering based on next_execution_time, falling back to sequence_number."""
        if self.next_execution_time == other.next_execution_time:
            return self.sequence_number < other.sequence_number
        return self.next_execution_time < other.next_execution_time

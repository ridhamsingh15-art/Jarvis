import time
from typing import Dict, Any

from core.events import EventBus
from core.models import Identifier, Event
from core.tasks import TaskManager, TaskDefinition, TaskStatus
from core.workflows import WorkflowManager, WorkflowDefinition

from .models import ScheduledJob, JobType, ScheduleStatus
from .triggers import Trigger
from .queue import SchedulerQueue
from .timers import TimerLoop
from .exceptions import SchedulerError

class SchedulerEngine:
    """Core logic mapping triggered jobs to their destination managers."""
    
    def __init__(self, event_bus: EventBus, task_manager: TaskManager, workflow_manager: WorkflowManager):
        self._event_bus = event_bus
        self._task_manager = task_manager
        self._workflow_manager = workflow_manager
        self._queue = SchedulerQueue()
        self._timer = TimerLoop(self._queue, self._dispatch)
        
        # Store raw definitions waiting to be submitted
        self._payload_store: Dict[str, Any] = {}
        # Store recurring triggers
        self._triggers: Dict[str, Trigger] = {}

    def start(self):
        self._timer.start()

    def stop(self):
        self._timer.stop()

    def schedule(self, payload: Any, trigger: Trigger, job_type: JobType) -> str:
        """Schedules a payload (TaskDefinition or WorkflowDefinition) using a Trigger."""
        now = time.time()
        fire_time = trigger.next_fire_time(now)
        
        if fire_time is None:
            raise SchedulerError("Trigger resolved to no future execution time.")
            
        t_type, t_meta = trigger.serialize()
        
        job = ScheduledJob(
            id=Identifier(),
            job_type=job_type,
            payload_id=payload.id,
            next_execution_time=fire_time,
            trigger_type=t_type,
            trigger_metadata=t_meta
        )
        
        # Store the payload so we can submit it when time arrives
        self._payload_store[payload.id.value] = payload
        self._triggers[job.id.value] = trigger
        
        self._queue.enqueue(job)
        self._timer.wake() # Interrupt sleep if this job is sooner
        
        self._event_bus.publish(Event(topic="task.scheduled", payload=job.to_dict(), source="scheduler"))
        return job.id.value
        
    def cancel(self, job_id: str) -> bool:
        if self._queue.remove(job_id):
            if job_id in self._triggers:
                del self._triggers[job_id]
            return True
        return False

    def _dispatch(self, job: ScheduledJob):
        """Called by TimerLoop when a job's time has arrived."""
        payload = self._payload_store.get(job.payload_id.value)
        if not payload:
            return # Payload deleted or invalid
            
        if job.job_type == JobType.TASK:
            self._task_manager.submit_task(payload)
        elif job.job_type == JobType.WORKFLOW:
            self._workflow_manager.submit_workflow(payload)
            self._workflow_manager.start_workflow(payload.id.value)
            
        self._event_bus.publish(Event(topic="task.released", payload=job.to_dict(), source="scheduler"))
        
        # Check if it's recurring
        trigger = self._triggers.get(job.id.value)
        if trigger:
            next_time = trigger.next_fire_time(time.time())
            if next_time is not None:
                # Reschedule
                next_job = ScheduledJob(
                    id=job.id, # Keep same schedule ID
                    job_type=job.job_type,
                    payload_id=job.payload_id,
                    next_execution_time=next_time,
                    trigger_type=job.trigger_type,
                    trigger_metadata=job.trigger_metadata
                )
                self._queue.enqueue(next_job)
            else:
                del self._triggers[job.id.value]

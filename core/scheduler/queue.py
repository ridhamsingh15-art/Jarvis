import heapq
import threading

from .models import ScheduledJob


class SchedulerQueue:
    """Thread-safe O(log n) min-heap for Scheduled Jobs."""
    
    def __init__(self):
        self._heap: list[ScheduledJob] = []
        self._lock = threading.Lock()
        self._not_empty = threading.Condition(self._lock)
        
    def enqueue(self, job: ScheduledJob) -> None:
        """Pushes a job onto the queue and notifies listeners."""
        with self._not_empty:
            heapq.heappush(self._heap, job)
            self._not_empty.notify()
            
    def dequeue(self) -> ScheduledJob | None:
        """Pops the soonest job. Returns None if empty."""
        with self._lock:
            if self._heap:
                return heapq.heappop(self._heap)
            return None
            
    def peek(self) -> ScheduledJob | None:
        """Returns the soonest job without popping it."""
        with self._lock:
            if self._heap:
                return self._heap[0]
            return None
            
    def wait_for_item(self, timeout: float | None = None) -> bool:
        """Blocks until an item is added or timeout expires. Returns True if notified."""
        with self._not_empty:
            if not self._heap:
                return self._not_empty.wait(timeout)
            return True
            
    def remove(self, job_id: str) -> bool:
        """O(n) removal of a specific job by ID (used for cancellation)."""
        with self._lock:
            for i, job in enumerate(self._heap):
                if job.id.value == job_id:
                    del self._heap[i]
                    heapq.heapify(self._heap)
                    return True
            return False
            
    def qsize(self) -> int:
        with self._lock:
            return len(self._heap)

    def size(self) -> int:
        return self.qsize()

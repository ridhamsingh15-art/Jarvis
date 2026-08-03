import threading
import time
from collections.abc import Callable

from .queue import SchedulerQueue


class TimerLoop:
    """Daemon thread that sleeps optimally until the next scheduled job is ready."""
    
    def __init__(self, queue: SchedulerQueue, dispatch_callback: Callable):
        self._queue = queue
        self._dispatch = dispatch_callback
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._wake_condition = threading.Condition() # Used to interrupt sleep if a sooner job arrives

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, name="Jarvis-Timer-Loop", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        self.wake()
        if self._thread:
            self._thread.join(timeout=2.0)

    def wake(self):
        """Interrupts the sleep immediately."""
        with self._wake_condition:
            self._wake_condition.notify()

    def _run_loop(self):
        while not self._stop_event.is_set():
            now = time.time()
            next_job = self._queue.peek()
            
            if not next_job:
                # No jobs. Sleep indefinitely until woken up by enqueue.
                with self._wake_condition:
                    # We wait with a max 1s timeout to periodically check stop_event safely
                    self._wake_condition.wait(1.0)
                continue
                
            sleep_time = next_job.next_execution_time - now
            
            if sleep_time <= 0:
                # Time to fire!
                job = self._queue.dequeue()
                if job:
                    self._dispatch(job)
            else:
                # Sleep until the job is ready, but allow interruption if a new sooner job arrives.
                with self._wake_condition:
                    # Bound the sleep to prevent hanging forever if stop_event is set
                    self._wake_condition.wait(min(sleep_time, 1.0))

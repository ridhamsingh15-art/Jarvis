import threading
import time
from collections.abc import Callable

from .enums import WorkerStatus
from .models import ExecutionContext
from .results import ExecutionResultBuilder


class WorkerThread(threading.Thread):
    """
    A single execution unit wrapping a native OS thread.
    Stays alive waiting for work to avoid thread creation overhead.
    Provides complete try/except isolation guaranteeing the thread survives panics.
    """
    def __init__(self, name: str, execution_callback: Callable[[ExecutionContext], dict], on_completion: Callable):
        super().__init__(name=name, daemon=True)
        self._execute = execution_callback
        self._on_completion = on_completion
        
        self.status = WorkerStatus.IDLE
        self._stop_event = threading.Event()
        self._work_condition = threading.Condition()
        self._current_context: ExecutionContext | None = None
        
    def assign(self, context: ExecutionContext) -> None:
        """Assigns a context to this worker and wakes it up."""
        with self._work_condition:
            self._current_context = context
            self.status = WorkerStatus.BUSY
            self._work_condition.notify()
            
    def stop(self) -> None:
        """Signals the worker to shutdown."""
        with self._work_condition:
            self.status = WorkerStatus.STOPPED
            self._stop_event.set()
            self._work_condition.notify()
            
    def _run_loop(self):
        while not self._stop_event.is_set():
            context = None
            
            with self._work_condition:
                if self._current_context is None and not self._stop_event.is_set():
                    self.status = WorkerStatus.IDLE
                    self._work_condition.wait()
                    
                if self._stop_event.is_set():
                    break
                    
                context = self._current_context
                
            if context:
                # Isolate execution
                start_time = time.time()
                result = None
                try:
                    # Action execution happens here
                    output = self._execute(context)
                    
                    if context.token.is_cancelled:
                        result = ExecutionResultBuilder.failure(context.task, f"Cancelled: {context.token.reason}", start_time)
                    else:
                        result = ExecutionResultBuilder.success(context.task, output, start_time)
                        
                except Exception as e:  # noqa: BLE001
                    # Catch-all isolation for ANY internal exception inside the action
                    result = ExecutionResultBuilder.failure(context.task, f"Execution Panic: {e!s}", start_time)
                    
                finally:
                    with self._work_condition:
                        self._current_context = None
                        self.status = WorkerStatus.IDLE
                    # Notify the pool that this worker finished
                    self._on_completion(self, context, result)

    def run(self):
        self._run_loop()

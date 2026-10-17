import logging
import threading
import time
from collections.abc import Callable

from .enums import WorkerStatus
from .models import ExecutionContext
from .results import ExecutionResultBuilder

logger = logging.getLogger(__name__)


class WorkerThread(threading.Thread):
    """A reusable worker thread that cooperatively cancels work during shutdown."""

    def __init__(self, name: str, execution_callback: Callable[[ExecutionContext], dict], on_completion: Callable):
        super().__init__(name=name, daemon=True)
        self._execute = execution_callback
        self._on_completion = on_completion
        self.status = WorkerStatus.IDLE
        self._stop_event = threading.Event()
        self._work_condition = threading.Condition()
        self._current_context: ExecutionContext | None = None

    def assign(self, context: ExecutionContext) -> None:
        """Assign one context; reject work once shutdown starts or while busy."""
        with self._work_condition:
            if self._stop_event.is_set() or self.status == WorkerStatus.STOPPED:
                raise RuntimeError(f"Worker {self.name} is stopping")
            if self._current_context is not None or self.status == WorkerStatus.BUSY:
                raise RuntimeError(f"Worker {self.name} already has assigned work")
            self._current_context = context
            self.status = WorkerStatus.BUSY
            self._work_condition.notify()

    def stop(self) -> None:
        """Request shutdown and cooperatively cancel any active or pending task."""
        with self._work_condition:
            if self._current_context is not None:
                self._current_context.token.cancel()
            self.status = WorkerStatus.STOPPED
            self._stop_event.set()
            self._work_condition.notify_all()

    def _run_loop(self) -> None:
        while True:
            with self._work_condition:
                while self._current_context is None and not self._stop_event.is_set():
                    self.status = WorkerStatus.IDLE
                    self._work_condition.wait()

                # A pending context is still consumed after stop, but only to emit
                # a cancellation result; it must never disappear in RUNNING state.
                if self._current_context is None and self._stop_event.is_set():
                    self.status = WorkerStatus.STOPPED
                    return
                context = self._current_context

            if context is None:
                continue

            start_time = time.time()
            try:
                if self._stop_event.is_set() or context.token.is_cancelled:
                    reason = "executor shutting down"
                    result = ExecutionResultBuilder.failure(
                        context.task, f"Cancelled: {reason}", start_time
                    )
                else:
                    output = self._execute(context)
                    if context.token.is_cancelled:
                        reason = "execution cancelled"
                        result = ExecutionResultBuilder.failure(
                            context.task, f"Cancelled: {reason}", start_time
                        )
                    else:
                        result = ExecutionResultBuilder.success(context.task, output, start_time)
            except Exception as exc:
                logger.exception("Worker %s failed while executing task", self.name)
                result = ExecutionResultBuilder.failure(
                    context.task, f"Execution Panic: {type(exc).__name__}", start_time
                )
            finally:
                with self._work_condition:
                    self._current_context = None
                    self.status = WorkerStatus.STOPPED if self._stop_event.is_set() else WorkerStatus.IDLE
                    self._work_condition.notify_all()

            try:
                self._on_completion(self, context, result)
            except Exception:
                # The callback is infrastructure code; report its failure without
                # allowing one callback exception to silently kill the worker loop.
                logger.exception("Worker %s completion callback failed", self.name)

            if self._stop_event.is_set():
                return

    def run(self) -> None:
        self._run_loop()

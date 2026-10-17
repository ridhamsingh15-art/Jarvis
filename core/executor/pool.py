import threading
import time
from collections.abc import Callable

from .enums import WorkerStatus
from .worker import WorkerThread


class WorkerPool:
    """Manages a bounded pool of worker threads with joined shutdown."""

    def __init__(self, name: str, min_workers: int, max_workers: int, execute_callback: Callable, completion_callback: Callable):
        if min_workers < 0 or max_workers < 1 or min_workers > max_workers:
            raise ValueError("worker bounds must satisfy 0 <= min_workers <= max_workers and max_workers >= 1")
        self._name = name
        self._min = min_workers
        self._max = max_workers
        self._execute = execute_callback
        self._completion = completion_callback
        self._workers: list[WorkerThread] = []
        self._lock = threading.Lock()
        for _ in range(self._min):
            self._spawn_worker()

    def _prune_dead_workers(self) -> None:
        self._workers = [worker for worker in self._workers if worker.is_alive()]

    def _spawn_worker(self) -> WorkerThread | None:
        """Spawn a worker if the live-worker count is below the configured cap."""
        with self._lock:
            self._prune_dead_workers()
            if len(self._workers) >= self._max:
                return None
            worker = WorkerThread(
                name=f"{self._name}-Worker-{len(self._workers) + 1}",
                execution_callback=self._execute,
                on_completion=self._completion,
            )
            self._workers.append(worker)
            worker.start()
            return worker

    def acquire_idle_worker(self) -> WorkerThread | None:
        """Return an idle worker or scale up if capacity permits."""
        with self._lock:
            self._prune_dead_workers()
            for worker in self._workers:
                if worker.status == WorkerStatus.IDLE and worker.is_alive():
                    return worker
        return self._spawn_worker()

    def shutdown(self, timeout: float = 2.0) -> None:
        """Request cancellation and join workers within a shared time budget.

        Threads that ignore cooperative cancellation remain tracked, rather than
        being discarded from the pool's diagnostics.
        """
        if timeout < 0:
            raise ValueError("timeout must be non-negative")
        with self._lock:
            workers = list(self._workers)
        for worker in workers:
            worker.stop()

        deadline = time.monotonic() + timeout
        for worker in workers:
            worker.join(timeout=max(0.0, deadline - time.monotonic()))

        with self._lock:
            self._prune_dead_workers()

    def get_stats(self) -> dict[str, int]:
        with self._lock:
            self._prune_dead_workers()
            busy = sum(1 for worker in self._workers if worker.status == WorkerStatus.BUSY)
            idle = sum(1 for worker in self._workers if worker.status == WorkerStatus.IDLE)
            return {
                "total_workers": len(self._workers),
                "busy_workers": busy,
                "idle_workers": idle,
            }

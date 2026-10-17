"""Regression tests for executor shutdown and queued-task lifecycle."""
from __future__ import annotations

import threading
from collections import deque
from types import SimpleNamespace
from unittest.mock import MagicMock

from core.executor.dispatcher import TaskDispatcher


class _Queue:
    def __init__(self, task: object) -> None:
        self.items = deque([task])
        self.lock = threading.Lock()
        self.dequeued = threading.Event()

    def dequeue(self):
        with self.lock:
            if self.items:
                task = self.items.popleft()
                self.dequeued.set()
                return task
            return None

    def enqueue(self, task) -> None:
        with self.lock:
            self.items.append(task)


def test_dispatcher_requeues_task_when_shutdown_prevents_worker_assignment() -> None:
    task = SimpleNamespace(task_id=SimpleNamespace(value="queued-1"))
    queue = _Queue(task)
    task_manager = SimpleNamespace(_queue=queue)
    no_worker = threading.Event()

    class UnavailablePool:
        def acquire_idle_worker(self):
            no_worker.set()

    dispatcher = TaskDispatcher(
        task_manager=task_manager,
        pool=UnavailablePool(),
        timeout_enforcer=MagicMock(),
        engine=MagicMock(),
    )
    dispatcher.start()
    assert queue.dequeued.wait(timeout=1)
    assert no_worker.wait(timeout=1)
    dispatcher.stop()

    with queue.lock:
        assert list(queue.items) == [task]

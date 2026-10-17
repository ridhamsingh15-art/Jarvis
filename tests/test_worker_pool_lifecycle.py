"""Regression tests for cooperative worker shutdown and bounded joins."""
from __future__ import annotations

import threading
import time

import pytest

from core.executor.models import ExecutionContext
from core.executor.pool import WorkerPool
from core.executor.worker import WorkerThread
from core.models import Identifier
from core.tasks import Task, TaskStatus


def _context(task_id: str) -> ExecutionContext:
    return ExecutionContext(task=Task(task_id=Identifier(task_id), status=TaskStatus.RUNNING))


def test_pool_shutdown_cancels_cooperative_action_and_joins_worker() -> None:
    started = threading.Event()
    completed = []

    def execute(context):
        started.set()
        while not context.token.is_cancelled:
            time.sleep(0.01)
        return {"observed_cancel": True}

    pool = WorkerPool(
        name="lifecycle-test",
        min_workers=1,
        max_workers=1,
        execute_callback=execute,
        completion_callback=lambda worker, context, result: completed.append(result),
    )
    worker = pool.acquire_idle_worker()
    assert worker is not None
    worker.assign(_context("active-1"))
    assert started.wait(timeout=1)

    pool.shutdown(timeout=1.0)

    assert not worker.is_alive()
    assert len(completed) == 1
    assert completed[0].success is False
    assert "Cancelled" in (completed[0].error_message or "")


def test_shutdown_timeout_keeps_unresponsive_worker_tracked() -> None:
    release = threading.Event()
    started = threading.Event()
    completed = []

    def execute(_context):
        started.set()
        release.wait(timeout=2)
        return {"finished": True}

    pool = WorkerPool(
        name="stuck-worker-test",
        min_workers=1,
        max_workers=1,
        execute_callback=execute,
        completion_callback=lambda worker, context, result: completed.append(result),
    )
    worker = pool.acquire_idle_worker()
    assert worker is not None
    worker.assign(_context("stuck-1"))
    assert started.wait(timeout=1)

    pool.shutdown(timeout=0.01)
    assert worker.is_alive()
    assert pool.get_stats() == {"total_workers": 1, "busy_workers": 0, "idle_workers": 0}

    release.set()
    worker.join(timeout=1)
    assert not worker.is_alive()
    assert len(completed) == 1
    assert completed[0].success is False
    assert pool.get_stats()["total_workers"] == 0


def test_stopped_worker_rejects_new_assignment() -> None:
    worker = WorkerThread("stopped-worker-test", lambda _context: {}, lambda *_args: None)
    worker.start()
    worker.stop()
    worker.join(timeout=1)
    assert not worker.is_alive()

    with pytest.raises(RuntimeError, match="stopping"):
        worker.assign(_context("never-run"))

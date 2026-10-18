import importlib.util
import threading
from pathlib import Path

import pytest

from core.executor.action_registry import ActionRegistry
from core.executor.executor import ExecutionEngine
from core.task import Task, TaskStatus


@pytest.mark.parametrize("status", [TaskStatus.RUNNING, TaskStatus.COMPLETED, TaskStatus.FAILED])
def test_execution_engine_does_not_invoke_handler_for_non_runnable_task(status):
    calls = []
    registry = ActionRegistry()
    registry.register("write_file", lambda _context, **kwargs: calls.append(kwargs))
    engine = ExecutionEngine(registry)
    task = Task(tool="file", action="write_file", args={"path": "x"}, status=status)

    result = engine.execute(task)

    assert result is task
    assert task.status is status
    assert calls == []


def test_execution_engine_still_executes_pending_tasks():
    registry = ActionRegistry()
    registry.register("read_file", lambda _context, **kwargs: {"content": kwargs["path"]})
    engine = ExecutionEngine(registry)
    task = Task(tool="file", action="read_file", args={"path": "example.txt"})

    result = engine.execute(task)

    assert result is task
    assert task.status is TaskStatus.COMPLETED
    assert task.result == {"content": "example.txt"}


def test_execution_engine_claims_concurrent_calls_exactly_once():
    entered = threading.Event()
    release = threading.Event()
    returned = threading.Event()
    call_lock = threading.Lock()
    calls = []
    registry = ActionRegistry()

    def slow_handler(_context, **kwargs):
        with call_lock:
            calls.append(kwargs)
        entered.set()
        assert release.wait(timeout=2)
        return {"ok": True}

    registry.register("write_file", slow_handler)
    engine = ExecutionEngine(registry)
    task = Task(tool="file", action="write_file", args={"path": "race.txt"})
    start = threading.Barrier(3)

    def run():
        start.wait(timeout=1)
        engine.execute(task)
        returned.set()

    threads = [threading.Thread(target=run, daemon=True) for _ in range(2)]
    for thread in threads:
        thread.start()
    start.wait(timeout=1)

    try:
        assert entered.wait(timeout=1)
        # The non-owning invocation must return while the first handler is still blocked.
        assert returned.wait(timeout=1)
        with call_lock:
            assert len(calls) == 1
        assert task.status is TaskStatus.RUNNING
    finally:
        release.set()
    for thread in threads:
        thread.join(timeout=2)
        assert not thread.is_alive()

    assert len(calls) == 1
    assert task.status is TaskStatus.COMPLETED
    assert task.result == {"ok": True}


def test_registered_legacy_executor_does_not_repeat_completed_task():
    # core/executor.py is shadowed by the core/executor/ package during ordinary import,
    # so load the legacy module explicitly to keep its contract from drifting.
    source = Path(__file__).resolve().parents[1] / "core" / "executor.py"
    spec = importlib.util.spec_from_file_location("jarvis_legacy_executor_under_test", source)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    calls = []

    class Tool:
        def execute(self, action, args):
            calls.append((action, args))
            return {"ok": True}

    class Registry:
        def get_executor(self, _tool):
            return Tool()

    engine = module.Executor(Registry())
    task = Task(tool="file", action="write_file", args={"path": "already-written.txt"})
    task.start()
    task.complete({"already": "completed"})

    result = engine.execute(task)

    assert result is task
    assert task.status is TaskStatus.COMPLETED
    assert task.result == {"already": "completed"}
    assert calls == []


def test_retrying_task_can_be_claimed_for_a_new_attempt():
    registry = ActionRegistry()
    registry.register("read_file", lambda _context, **_kwargs: {"ok": True})
    engine = ExecutionEngine(registry)
    task = Task(tool="file", action="read_file")
    task.start()
    task.fail("temporary failure")
    task.retry()

    result = engine.execute(task)

    assert result is task
    assert task.status is TaskStatus.COMPLETED
    assert task.result == {"ok": True}


def test_handler_exception_after_side_effect_is_marked_outcome_unknown(tmp_path: Path):
    target = tmp_path / "side-effect-before-error.txt"
    calls = []

    def side_effect_then_raise(_context, **_kwargs):
        calls.append("invoked")
        target.write_text("changed", encoding="utf-8")
        raise RuntimeError("failure after mutation")

    registry = ActionRegistry()
    registry.register("write_file", side_effect_then_raise)
    engine = ExecutionEngine(registry)
    task = Task(tool="file", action="write_file", args={"path": str(target)})

    result = engine.execute(task)

    assert result is task
    assert target.read_text(encoding="utf-8") == "changed"
    assert calls == ["invoked"]
    assert task.status is TaskStatus.FAILED
    assert "OUTCOME UNKNOWN" in task.error
    assert "do not automatically retry" in task.error.lower()

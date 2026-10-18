"""Regression coverage for Agent tool timeout and future lifecycle."""
from __future__ import annotations

import threading
from pathlib import Path
from unittest.mock import MagicMock

from core.agent import Agent
from core.cognition.conversation import ConversationResponse
from core.execution_policy import ExecutionPolicy
from core.routing.intent_classifier import IntentType
from core.task import Task, TaskStatus


class _BlockingExecutor:
    def __init__(self) -> None:
        self.started = threading.Event()
        self.release = threading.Event()
        self.finished = threading.Event()
        self.received_task: Task | None = None

    def execute(self, task: Task) -> Task:
        self.received_task = task
        task.start()
        self.started.set()
        try:
            self.release.wait(timeout=2)
            task.complete("late success")
            return task
        finally:
            self.finished.set()


def test_late_executor_completion_cannot_mutate_timed_out_task() -> None:
    executor = _BlockingExecutor()
    cognitive = MagicMock()
    cognitive.process_fast.return_value = ConversationResponse(
        type="ACTION",
        message="Starting a controlled test action.",
        tool="windows",
        action="open_app",
        parameters={"app": "notepad"},
    )
    agent = Agent(
        planner=MagicMock(),
        validator=MagicMock(),
        executor=executor,
        cognitive_manager=cognitive,
        execution_policy=ExecutionPolicy(allow_destructive_from_core=True),
        default_tool_timeout=0.05,
    )

    try:
        results = agent.run("Run the controlled test action", intent=IntentType.CHAT)
        timed_out_task = next(task for task in results if task.tool == "windows")
        assert executor.started.wait(timeout=1)
        assert timed_out_task.status == TaskStatus.FAILED
        assert "timed out" in timed_out_task.error.lower()

        executor.release.set()
        assert executor.finished.wait(timeout=1)
        assert executor.received_task is not None
        assert executor.received_task is not timed_out_task
        assert executor.received_task.status == TaskStatus.COMPLETED
        assert timed_out_task.status == TaskStatus.FAILED
        assert "timed out" in timed_out_task.error.lower()
    finally:
        executor.release.set()
        agent.close()



def test_agent_close_cancels_queued_execution_future() -> None:
    release = threading.Event()
    executor_called = threading.Event()

    class _NeverReachedExecutor:
        def execute(self, task: Task) -> Task:
            executor_called.set()
            task.start()
            task.complete("unexpected")
            return task

    agent = Agent(
        planner=MagicMock(),
        validator=MagicMock(),
        executor=_NeverReachedExecutor(),
        cognitive_manager=MagicMock(),
    )
    blockers = [agent._executor_pool.submit(release.wait, 2) for _ in range(4)]
    queued = agent._submit_execution_task(Task(tool="windows", action="open_app"))
    assert not queued.running()

    agent.close()
    try:
        assert queued.cancelled()
        assert not executor_called.is_set()
        with agent._execution_futures_lock:
            assert not agent._execution_futures
    finally:
        release.set()
        for blocker in blockers:
            blocker.result(timeout=1)



def test_stalled_handler_does_not_block_unrelated_task_and_timeout_is_uncertain(tmp_path: Path) -> None:
    late_side_effect = tmp_path / "late-side-effect.txt"

    class BlockFirstExecutor:
        def __init__(self) -> None:
            self.started = threading.Event()
            self.release = threading.Event()
            self.finished = threading.Event()

        def execute(self, task: Task) -> Task:
            task.start()
            if task.args.get("app") == "notepad":
                self.started.set()
                try:
                    self.release.wait(timeout=5)
                    late_side_effect.write_text("mutation after timeout", encoding="utf-8")
                    task.complete("late completion")
                finally:
                    self.finished.set()
            else:
                task.complete("unrelated task completed")
            return task

    executor = BlockFirstExecutor()
    cognitive = MagicMock()
    cognitive.process_fast.return_value = ConversationResponse(
        type="ACTION",
        message="Start a controlled blocking action.",
        tool="windows",
        action="open_app",
        parameters={"app": "notepad"},
    )
    agent = Agent(
        planner=MagicMock(),
        validator=MagicMock(),
        executor=executor,
        cognitive_manager=cognitive,
        execution_policy=ExecutionPolicy(allow_destructive_from_core=True),
        default_tool_timeout=0.05,
    )
    try:
        first_results = agent.run("Run the controlled blocking action", intent=IntentType.CHAT)
        first_task = next(task for task in first_results if task.tool == "windows")
        assert executor.started.wait(timeout=1)
        assert first_task.status == TaskStatus.FAILED
        assert "outcome unknown" in first_task.error.lower()
        assert "do not automatically retry" in first_task.error.lower()
        assert agent.last_trace is not None
        assert agent.last_trace.status == "outcome_unknown"
        assert "OUTCOME UNKNOWN" in str(agent.last_trace.final_response)
        assert not late_side_effect.exists()

        cognitive.process_fast.return_value = ConversationResponse(
            type="ACTION",
            message="Run an unrelated action.",
            tool="windows",
            action="open_app",
            parameters={"app": "calculator"},
        )
        second_results = agent.run("Run an unrelated action", intent=IntentType.CHAT)
        second_task = next(task for task in second_results if task.tool == "windows")
        assert second_task.status == TaskStatus.COMPLETED
        assert second_task.result == "unrelated task completed"

        executor.release.set()
        assert executor.finished.wait(timeout=1)
        assert late_side_effect.read_text(encoding="utf-8") == "mutation after timeout"
        assert first_task.status == TaskStatus.FAILED
        assert "outcome unknown" in first_task.error.lower()
    finally:
        executor.release.set()
        agent.close()



def test_agent_close_returns_within_bound_for_stalled_running_handler() -> None:
    import time

    class StalledExecutor:
        def __init__(self) -> None:
            self.started = threading.Event()
            self.release = threading.Event()
            self.finished = threading.Event()

        def execute(self, task: Task) -> Task:
            task.start()
            self.started.set()
            try:
                self.release.wait(timeout=5)
                task.complete("finished after release")
                return task
            finally:
                self.finished.set()

    executor = StalledExecutor()
    cognitive = MagicMock()
    cognitive.process_fast.return_value = ConversationResponse(
        type="ACTION",
        message="Start a controlled stalled action.",
        tool="windows",
        action="open_app",
        parameters={"app": "notepad"},
    )
    agent = Agent(
        planner=MagicMock(),
        validator=MagicMock(),
        executor=executor,
        cognitive_manager=cognitive,
        execution_policy=ExecutionPolicy(allow_destructive_from_core=True),
        default_tool_timeout=0.05,
    )
    try:
        results = agent.run("Run the controlled stalled action", intent=IntentType.CHAT)
        timed_out = next(task for task in results if task.tool == "windows")
        assert executor.started.wait(timeout=1)
        assert timed_out.status == TaskStatus.FAILED
        started_at = time.monotonic()
        agent.close()
        assert time.monotonic() - started_at < 0.5
        assert not executor.finished.is_set()
    finally:
        executor.release.set()
        assert executor.finished.wait(timeout=1)
        agent.close()


def test_non_task_executor_result_fails_closed_without_escaping_process_task() -> None:
    class WrongTypeExecutor:
        def execute(self, _task):
            # Contract violation after invocation: caller cannot infer the side-effect outcome.
            return {"stdout": "unverified payload"}

    agent = Agent(
        planner=MagicMock(),
        validator=MagicMock(),
        executor=WrongTypeExecutor(),
        execution_policy=ExecutionPolicy(allow_destructive_from_core=True),
        default_tool_timeout=0.2,
    )
    task = Task(tool="file", action="read_file", args={"path": "isolated-probe.txt"})

    try:
        result = agent._process_task(task)

        assert result is task
        assert result.status is TaskStatus.FAILED
        assert "OUTCOME UNKNOWN" in result.error
        assert "dict" in result.error
        assert "Do not automatically retry" in result.error
    finally:
        agent.close()


def test_executor_failed_task_without_no_side_effect_proof_becomes_unknown() -> None:
    class OrdinaryFailureExecutor:
        def execute(self, task: Task) -> Task:
            task.start()
            task.fail("ordinary executor failure after dispatch")
            return task

    agent = Agent(
        planner=MagicMock(),
        validator=MagicMock(),
        executor=OrdinaryFailureExecutor(),
        execution_policy=ExecutionPolicy(allow_destructive_from_core=True),
        default_tool_timeout=0.2,
    )
    task = Task(tool="file", action="write_file", args={"path": "failure-probe.txt"})

    try:
        result = agent._process_task(task)
        assert result.status is TaskStatus.FAILED
        assert "OUTCOME UNKNOWN" in result.error
        assert "Do not automatically retry" in result.error
    finally:
        agent.close()


def test_executor_exception_after_dispatch_becomes_unknown() -> None:
    calls: list[str] = []
    side_effects: list[str] = []

    class RaisingExecutor:
        def execute(self, _task: Task) -> Task:
            calls.append("called")
            side_effects.append("possible-side-effect")
            raise RuntimeError("executor raised after dispatch")

    agent = Agent(
        planner=MagicMock(),
        validator=MagicMock(),
        executor=RaisingExecutor(),
        execution_policy=ExecutionPolicy(allow_destructive_from_core=True),
        default_tool_timeout=0.2,
    )
    task = Task(tool="file", action="write_file", args={"path": "failure-probe.txt"})

    try:
        result = agent._process_task(task)
        assert calls == ["called"]
        assert side_effects == ["possible-side-effect"]
        assert result.status is TaskStatus.FAILED
        assert "OUTCOME UNKNOWN" in result.error
        assert "do not automatically retry" in result.error.lower()
    finally:
        agent.close()


def test_internal_type_error_does_not_retry_task_processing_callback() -> None:
    agent = Agent(
        planner=MagicMock(),
        validator=MagicMock(),
        executor=MagicMock(),
        default_tool_timeout=0.2,
        max_tool_iterations=1,
    )
    task = Task(tool="fake", action="record_probe", args={})
    agent._planner.plan.return_value = [task]
    calls: list[dict[str, object]] = []
    simulated_side_effects: list[str] = []

    def faulty_processor(processing_task: Task, **kwargs: object) -> Task:
        calls.append(dict(kwargs))
        simulated_side_effects.append("simulated-side-effect")
        raise TypeError("internal result parsing failed after side effect")

    agent._process_task = faulty_processor  # type: ignore[method-assign]
    try:
        results = agent.run("isolated internal TypeError probe", intent=IntentType.TOOL)
        failed_task = next(result for result in results if result.tool == "fake")

        assert len(calls) == 1
        assert calls == [{"user_confirmed": False}]
        assert simulated_side_effects == ["simulated-side-effect"]
        assert failed_task.status is TaskStatus.FAILED
        assert "OUTCOME UNKNOWN" in failed_task.error
        assert "do not automatically retry" in failed_task.error.lower()
    finally:
        agent.close()


def test_signature_compatibility_does_not_retry_one_argument_processor() -> None:
    agent = Agent(
        planner=MagicMock(),
        validator=MagicMock(),
        executor=MagicMock(),
        max_tool_iterations=1,
    )
    task = Task(tool="fake", action="one_arg", args={})
    agent._planner.plan.return_value = [task]
    calls: list[Task] = []

    def legacy_processor(processing_task: Task) -> Task:
        calls.append(processing_task)
        processing_task.start()
        processing_task.complete("legacy compatible")
        return processing_task

    agent._process_task = legacy_processor  # type: ignore[method-assign]
    try:
        results = agent.run("isolated legacy processor probe", intent=IntentType.TOOL)
        assert calls == [task]
        assert next(result for result in results if result.tool == "fake").status is TaskStatus.COMPLETED
    finally:
        agent.close()


def test_callback_exception_after_terminal_success_still_reports_unknown() -> None:
    agent = Agent(
        planner=MagicMock(),
        validator=MagicMock(),
        executor=MagicMock(),
        execution_policy=ExecutionPolicy(allow_destructive_from_core=True),
        default_tool_timeout=0.2,
        max_tool_iterations=3,
    )
    task = Task(tool="fake", action="record_probe", args={})
    agent._planner.plan.return_value = [task]
    calls: list[str] = []
    side_effects: list[str] = []

    def faulty_processor(processing_task: Task, **kwargs: object) -> Task:
        calls.append("called")
        side_effects.append("possible-external-side-effect")
        processing_task.start()
        processing_task.complete("success-looking result")
        processing_task.args = "malformed-after-side-effect"
        raise TypeError("callback failed after terminal state was set")

    agent._process_task = faulty_processor  # type: ignore[method-assign]
    try:
        results = agent.run("terminal callback failure probe", intent=IntentType.TOOL)
        failed_task = next(result for result in results if result.tool == "fake")

        assert calls == ["called"]
        assert side_effects == ["possible-external-side-effect"]
        assert failed_task.status is TaskStatus.FAILED
        assert "OUTCOME UNKNOWN" in failed_task.error
        assert "do not automatically retry" in failed_task.error.lower()
        assert failed_task.result != "success-looking result"
        assert failed_task.args == {"_invalid_args_type": "str"}
        assert agent.last_trace is not None
        assert agent.last_trace.status == "outcome_unknown"
        assert "OUTCOME UNKNOWN" in str(agent.last_trace.final_response)
        assert "success-looking result" not in str(agent.last_trace.final_response)
    finally:
        agent.close()

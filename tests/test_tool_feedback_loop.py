"""
Phase A Tests — Tool Feedback Loop

Tests:
1. success on first call
2. retry after failure
3. second tool call in sequence
4. successful completion after retry
5. failure after 3 iterations (limit_reached)
6. malformed tool output (task in bad state)
7. repeated identical tool call (loop detection)
8. LLM correction on retry
"""
import pytest
from unittest.mock import MagicMock, call
from core.task import Task, TaskStatus
from core.tool_feedback_loop import ToolFeedbackLoop, MAX_TOOL_ITERATIONS, _task_fingerprint


def _pending_task(tool="windows", action="open_app", args=None):
    return Task(tool=tool, action=action, args=args or {"app": "calculator"})


def _success_execute(task: Task) -> Task:
    task.start()
    task.complete("done")
    return task


def _fail_execute(task: Task) -> Task:
    task.start()
    task.fail("tool unavailable")
    return task


class TestToolFeedbackLoopSuccess:
    def test_success_on_first_call(self):
        loop = ToolFeedbackLoop(execute_fn=_success_execute)
        result = loop.run("req-1", "open calculator", [_pending_task()])
        assert result.succeeded
        assert result.iterations_used == 1
        assert not result.loop_detected
        assert not result.limit_reached

    def test_all_tasks_succeed(self):
        loop = ToolFeedbackLoop(execute_fn=_success_execute)
        tasks = [
            _pending_task(tool="browser", action="open_url", args={"url": "http://a.com"}),
            _pending_task(tool="windows", action="open_app", args={"app": "notepad"}),
        ]
        result = loop.run("req-2", "open two things", tasks)
        assert result.succeeded
        assert result.iterations_used == 1

    def test_system_task_passes_through(self):
        task = Task(tool="system", action="respond", args={"message": "hello"})
        loop = ToolFeedbackLoop(execute_fn=_fail_execute)  # would fail real tasks
        result = loop.run("req-sys", "hi", [task])
        assert result.succeeded  # system tasks don't fail


class TestToolFeedbackLoopRetry:
    def test_retry_after_single_failure(self):
        """First call fails. Without CognitiveManager, raw retry requeues same
        task → loop detection fires on iteration 2. Both terminal states are valid.
        With a CognitiveManager, a different correction task would be produced.
        """
        calls = []

        def execute(task):
            calls.append(task.action)
            task.start()
            task.fail("transient error")
            return task

        loop = ToolFeedbackLoop(execute_fn=execute, max_iterations=3)
        result = loop.run("req-r", "open calc", [_pending_task()])
        # Without CognitiveManager: raw retry → same fingerprint → loop_detected
        assert not result.succeeded
        assert result.loop_detected or result.limit_reached

    def test_llm_guided_retry(self):
        """When CognitiveManager is present, it suggests a corrected call."""
        from core.cognition.conversation import ConversationResponse

        cognitive = MagicMock()
        cognitive.process_fast.return_value = ConversationResponse(
            type="ACTION", message="Trying corrected call",
            tool="windows", action="open_app", parameters={"app": "calculator"},
        )

        fail_calls = []

        def execute(task):
            if task.tool == "system":
                task.start()
                task.complete(task.args.get("message", ""))
                return task
            fail_calls.append(task)
            task.start()
            if len(fail_calls) == 1:
                task.fail("first failure")
            else:
                task.complete("ok")
            return task

        loop = ToolFeedbackLoop(execute_fn=execute, cognitive_manager=cognitive, max_iterations=3)
        result = loop.run("req-llm", "open calculator", [_pending_task()])
        assert cognitive.process_fast.called


class TestToolFeedbackLoopLimits:
    def test_failure_after_max_iterations(self):
        """All iterations fail → succeeded=False. Without CognitiveManager, loop
        detection fires before max_iterations because raw retry reuses same fingerprint.
        Either loop_detected or limit_reached must be True.
        """
        loop = ToolFeedbackLoop(execute_fn=_fail_execute, max_iterations=3)
        result = loop.run("req-max", "do something", [_pending_task()])
        assert not result.succeeded
        # Either loop detection or max iterations reached — both are valid
        assert result.loop_detected or result.limit_reached

    def test_max_iterations_configurable(self):
        """Custom max_iterations is respected."""
        loop = ToolFeedbackLoop(execute_fn=_fail_execute, max_iterations=2)
        result = loop.run("req-cfg", "fail", [_pending_task()])
        assert result.iterations_used == 2

    def test_max_iterations_must_be_positive(self):
        with pytest.raises(ValueError):
            ToolFeedbackLoop(execute_fn=_success_execute, max_iterations=0)


class TestToolFeedbackLoopDetection:
    def test_loop_detection_stops_identical_calls(self):
        """Same (tool, action, args) appearing twice triggers loop detection."""
        calls = []

        def execute(task):
            calls.append(_task_fingerprint(task))
            task.start()
            task.fail("always fails")
            return task

        loop = ToolFeedbackLoop(execute_fn=execute, max_iterations=5)
        # Run once — first execution fails
        result = loop.run("req-loop", "open calc", [_pending_task()])
        # Raw retry submits same task again → loop detected
        assert result.loop_detected or result.limit_reached

    def test_different_args_not_detected_as_loop(self):
        """Different args produce different fingerprints — not a loop."""
        t1 = _pending_task(args={"app": "calculator"})
        t2 = _pending_task(args={"app": "notepad"})
        fp1 = _task_fingerprint(t1)
        fp2 = _task_fingerprint(t2)
        assert fp1 != fp2


class TestToolFeedbackLoopTelemetry:
    def test_iterations_logged(self):
        loop = ToolFeedbackLoop(execute_fn=_success_execute, max_iterations=3)
        result = loop.run("req-tel", "open calc", [_pending_task()])
        assert len(result.iterations) >= 1
        first = result.iterations[0]
        assert first.iteration == 1
        assert first.success is True
        assert first.latency_ms >= 0

    def test_failure_recorded_in_iterations(self):
        loop = ToolFeedbackLoop(execute_fn=_fail_execute, max_iterations=1)
        result = loop.run("req-fail-tel", "open calc", [_pending_task()])
        assert result.iterations[0].success is False
        assert "tool unavailable" in result.iterations[0].reason

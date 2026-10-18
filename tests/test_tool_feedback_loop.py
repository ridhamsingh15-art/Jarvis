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
from unittest.mock import MagicMock

import pytest

from core.task import Task
from core.tool_feedback_loop import (
    ToolFeedbackLoop,
    _task_fingerprint,
)


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
        loop.run("req-llm", "open calculator", [_pending_task()])
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

    def test_mixed_type_mapping_keys_have_stable_fingerprints(self):
        first = Task(tool="file", action="read_file", args={"path": "a.txt", 3: "metadata"})
        second = Task(tool="file", action="read_file", args={3: "metadata", "path": "a.txt"})

        assert _task_fingerprint(first) == _task_fingerprint(second)

    def test_cyclic_arguments_do_not_crash_fingerprinting(self):
        args = {}
        args["self"] = args
        task = Task(tool="file", action="read_file", args=args)

        assert _task_fingerprint(task) == _task_fingerprint(task)


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


class TestUnknownOutcomeStopsOrchestration:
    def test_unknown_outcome_is_not_retried_without_cognitive_manager(self):
        calls = []

        def execute(task):
            calls.append((task.tool, task.action))
            task.start()
            task.fail("OUTCOME UNKNOWN: external side effect may have occurred")
            return task

        loop = ToolFeedbackLoop(execute_fn=execute, max_iterations=3)
        result = loop.run("req-unknown-raw", "perform action", [_pending_task()])

        assert calls == [("windows", "open_app")]
        assert result.outcome_unknown is True
        assert result.succeeded is False
        assert result.iterations_used == 1
        assert "OUTCOME UNKNOWN" in result.final_response
        assert "Do not automatically retry" in result.final_response
        assert "reconcile external state" in result.final_response.lower()

    def test_unknown_outcome_stops_remaining_initial_batch_tasks(self):
        calls = []
        first = _pending_task(tool="file", action="write_file", args={"path": "a.txt"})
        second = _pending_task(tool="browser", action="open_url", args={"url": "https://example.invalid"})

        def execute(task):
            calls.append((task.tool, task.action))
            task.start()
            if task.tool == "file":
                task.fail("OUTCOME UNKNOWN: write may have happened")
            else:
                task.complete("unexpectedly executed")
            return task

        loop = ToolFeedbackLoop(execute_fn=execute, max_iterations=3)
        result = loop.run("req-unknown-batch", "write then browse", [first, second])

        assert calls == [("file", "write_file")]
        assert result.outcome_unknown is True
        assert second.status.value == "pending"
        assert "Not executed" in second.error
        assert "browser.open_url" in result.final_response
        assert "OUTCOME UNKNOWN" in result.final_response

    def test_execution_callback_exception_fails_closed_and_skips_model(self):
        from core.cognition.conversation import ConversationResponse

        cognitive = MagicMock()
        cognitive.process_fast.return_value = ConversationResponse(
            type="ACTION", message="Try again", tool="windows",
            action="open_app", parameters={"app": "calculator"},
        )
        calls = []

        def execute(task):
            calls.append((task.tool, task.action))
            raise TypeError("callback failed after possible side effect")

        loop = ToolFeedbackLoop(execute_fn=execute, cognitive_manager=cognitive, max_iterations=3)
        result = loop.run("req-unknown-exception", "open calculator", [_pending_task()])

        assert calls == [("windows", "open_app")]
        assert cognitive.process_fast.call_count == 0
        assert result.outcome_unknown is True
        assert result.succeeded is False
        assert "OUTCOME UNKNOWN" in result.final_response
        assert any(
            task.status.value == "failed" and "outcome unknown" in task.error.lower()
            for task in result.tasks if task.tool != "system"
        )

    def test_invalid_executor_return_is_not_retried(self):
        calls = []

        def execute(task):
            calls.append(task.action)
            return {"status": "completed"}

        loop = ToolFeedbackLoop(execute_fn=execute, max_iterations=3)
        result = loop.run("req-invalid-result", "open calculator", [_pending_task()])

        assert calls == ["open_app"]
        assert result.outcome_unknown is True
        assert result.succeeded is False
        assert "expected Task" in result.final_response

    def test_unknown_outcome_overrides_model_success_claim(self):
        from core.cognition.conversation import ConversationResponse

        cognitive = MagicMock()
        cognitive.process_fast.return_value = ConversationResponse(
            type="RESPONSE", message="Done successfully; the operation completed."
        )
        response_task = Task(
            tool="system", action="respond",
            args={"message": "Done successfully; the operation completed."},
        )

        def execute(task):
            task.start()
            task.fail("OUTCOME UNKNOWN: the operation may have changed external state")
            return task

        loop = ToolFeedbackLoop(execute_fn=execute, cognitive_manager=cognitive, max_iterations=3)
        result = loop.run(
            "req-unknown-claim", "perform operation",
            [_pending_task(), response_task],
        )

        assert cognitive.process_fast.call_count == 0
        assert result.outcome_unknown is True
        assert result.succeeded is False
        assert "OUTCOME UNKNOWN" in result.final_response
        assert "Done successfully" not in result.final_response
        assert "reconcile external state" in result.final_response.lower()

    def test_nonterminal_executor_task_becomes_uncertain_failure(self):
        calls = []

        def execute(task):
            calls.append(task.action)
            task.start()
            return task  # violates the callback contract: it did not reach a terminal state

        loop = ToolFeedbackLoop(execute_fn=execute, max_iterations=3)
        result = loop.run("req-nonterminal", "open calculator", [_pending_task()])

        assert calls == ["open_app"]
        assert result.outcome_unknown is True
        assert result.succeeded is False
        assert "nonterminal Task status (running)" in result.final_response
        assert "Do not automatically retry" in result.final_response

    def test_malformed_task_args_after_possible_side_effect_fail_without_crashing(self):
        calls = []

        def execute(task):
            calls.append(task.action)
            task.start()
            task.complete("side effect may have happened")
            task.args = "not-a-mapping"
            raise TypeError("failure after possible side effect")

        loop = ToolFeedbackLoop(execute_fn=execute, max_iterations=3)
        result = loop.run("req-malformed-args", "perform operation", [_pending_task()])

        failed = next(task for task in result.tasks if task.tool != "system")
        assert calls == ["open_app"]
        assert result.outcome_unknown is True
        assert failed.status.value == "failed"
        assert failed.args == {"_invalid_args_type": "str"}
        assert "OUTCOME UNKNOWN" in failed.error
        assert "reconcile external state" in result.final_response.lower()

    def test_engine_handler_exception_stops_orchestration_after_side_effect(self, tmp_path):
        from core.executor.action_registry import ActionRegistry
        from core.executor.executor import ExecutionEngine

        target = tmp_path / "side-effect-before-exception.txt"
        calls = []

        def side_effect_then_raise(_context, **_kwargs):
            calls.append("write_file")
            target.write_text("changed", encoding="utf-8")
            raise RuntimeError("failed after mutation")

        registry = ActionRegistry()
        registry.register("write_file", side_effect_then_raise)
        registry.register("open_app", lambda _context, **_kwargs: calls.append("open_app"))
        engine = ExecutionEngine(registry)
        first = Task(tool="file", action="write_file", args={"path": str(target)})
        second = Task(tool="windows", action="open_app", args={"app": "calculator"})

        loop = ToolFeedbackLoop(execute_fn=engine.execute, max_iterations=3)
        result = loop.run("req-engine-uncertain", "write then open", [first, second])

        assert target.read_text(encoding="utf-8") == "changed"
        assert calls == ["write_file"]
        assert result.outcome_unknown is True
        assert result.succeeded is False
        assert "OUTCOME UNKNOWN" in result.final_response
        assert "windows.open_app" in result.final_response

    def test_precompleted_tool_task_is_not_executed_again(self):
        calls = []
        completed = _pending_task()
        completed.start()
        completed.complete("already completed")

        def execute(task):
            calls.append(task.action)
            return _success_execute(task)

        loop = ToolFeedbackLoop(execute_fn=execute, max_iterations=3)
        result = loop.run("req-already-completed", "open calculator", [completed])

        assert calls == []
        assert result.succeeded is True
        assert result.outcome_unknown is False
        assert completed.result == "already completed"

    def test_completed_system_response_is_idempotent(self):
        response = Task(tool="system", action="respond", args={"message": "hello"})
        response.start()
        response.complete("hello, already generated")

        loop = ToolFeedbackLoop(execute_fn=_success_execute)
        result = loop.run("req-completed-response", "hello", [response])

        assert result.succeeded is True
        assert response.status.value == "completed"
        assert result.final_response == "hello, already generated"

    def test_running_initial_task_is_not_dispatched_again(self):
        calls = []
        active = _pending_task()
        active.start()
        later = _pending_task(tool="browser", action="open_url", args={"url": "https://example.invalid"})

        def execute(task):
            calls.append(task.action)
            return _success_execute(task)

        loop = ToolFeedbackLoop(execute_fn=execute)
        result = loop.run("req-already-running", "open calculator", [active, later])

        assert calls == []
        assert result.outcome_unknown is True
        # The loop must not mutate another owner's in-flight task while refusing to replay it.
        assert active.status.value == "running"
        uncertain_result = next(
            task for task in result.tasks
            if task.tool == active.tool and task.action == active.action and task.status.value == "failed"
        )
        assert "OUTCOME UNKNOWN" in uncertain_result.error
        assert later.status.value == "pending"
        assert "Not executed" in later.error

    def test_preexisting_unknown_failure_is_never_retried(self):
        calls = []
        uncertain = _pending_task()
        uncertain.start()
        uncertain.fail("OUTCOME UNKNOWN: prior run may have opened the application")
        later = _pending_task(tool="browser", action="open_url", args={"url": "https://example.invalid"})

        def execute(task):
            calls.append(task.action)
            return _success_execute(task)

        loop = ToolFeedbackLoop(execute_fn=execute)
        result = loop.run("req-prior-unknown", "open calculator then browse", [uncertain, later])

        assert calls == []
        assert result.outcome_unknown is True
        assert result.succeeded is False
        assert "OUTCOME UNKNOWN" in result.final_response
        assert later.status.value == "pending"

    def test_known_failed_input_uses_controlled_retry_without_duplicate_history(self):
        calls = []
        previously_failed = _pending_task()
        previously_failed.start()
        previously_failed.fail("transient failure with known no-side-effect result")

        def execute(task):
            calls.append(task.action)
            return _success_execute(task)

        loop = ToolFeedbackLoop(execute_fn=execute)
        result = loop.run("req-known-retry", "open calculator", [previously_failed])

        tool_results = [task for task in result.tasks if task.tool != "system"]
        assert calls == ["open_app"]
        assert result.succeeded is True
        assert len(tool_results) == 1
        assert tool_results[0].status.value == "completed"
        assert tool_results[0].retry_count == 1

    def test_empty_task_list_is_not_reported_as_success(self):
        loop = ToolFeedbackLoop(execute_fn=_success_execute)
        result = loop.run("req-no-tasks", "do nothing", [])

        assert result.succeeded is False
        assert result.iterations_used == 0
        assert "no work was executed" in result.final_response.lower()

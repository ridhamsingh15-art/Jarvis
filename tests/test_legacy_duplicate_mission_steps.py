from __future__ import annotations

import json
from types import SimpleNamespace

from core.execution_policy import PolicyVerdict
from core.task import TaskStatus
from mission_control.execution import MissionExecutor
from mission_control.mission import Mission, MissionState


class AllowPolicy:
    def __init__(self):
        self.contexts = []

    def check(self, context):
        self.contexts.append(context)
        return SimpleNamespace(verdict=PolicyVerdict.ALLOW, reason="allowed")


class SuccessfulEngine:
    def __init__(self):
        self.calls = []

    def execute(self, task):
        self.calls.append((task.tool, task.action, dict(task.args)))
        task.status = TaskStatus.COMPLETED
        task.result = {"stdout": "ok", "stderr": "", "exit_code": 0, "paths": []}


def _step(action: str) -> str:
    return json.dumps({"tool": "file", "action": action, "args": {"path": "."}})


def test_legacy_executor_runs_repeated_step_occurrences_by_index(monkeypatch):
    from mission_control import crash_safe

    monkeypatch.setattr(crash_safe, "_verify_action_outcome", lambda *args, **kwargs: {"status": "verified", "method": "test"})
    monkeypatch.setattr(crash_safe, "_verify_file_mutation_outcome", lambda *args, **kwargs: {"status": "verified", "method": "test"})
    a = _step("list_directory")
    b = _step("read_file")
    mission = Mission(id="duplicate-occurrences", objective="run A, B, A", state=MissionState.RUNNING, steps=[a, b, a])
    policy = AllowPolicy()
    engine = SuccessfulEngine()
    executor = MissionExecutor(execution_engine=engine, policy=policy)

    for _ in range(4):
        if mission.state != MissionState.RUNNING:
            break
        executor.step(mission)

    assert [call[1] for call in engine.calls] == ["file.list_directory", "file.read_file", "file.list_directory"]
    assert [record["step_index"] for record in mission.step_results if record["status"] == "completed"] == [0, 1, 2]
    assert mission.state is MissionState.COMPLETED


def test_text_only_approval_does_not_authorize_duplicate_step_occurrences():
    duplicated = _step("delete")
    mission = Mission(
        id="duplicate-approval", objective="delete twice", state=MissionState.RUNNING,
        steps=[duplicated, duplicated], approved_steps=[duplicated],
    )
    policy = AllowPolicy()
    # Policy context is constructed before check; capture it with a confirmation verdict.
    policy.check = lambda context: (policy.contexts.append(context) or SimpleNamespace(
        verdict=PolicyVerdict.REQUIRE_CONFIRMATION, reason="requires confirmation"))
    executor = MissionExecutor(execution_engine=SuccessfulEngine(), policy=policy)
    executor.step(mission)

    assert policy.contexts
    assert policy.contexts[0].user_confirmed is False
    assert mission.state is MissionState.WAITING_APPROVAL
    assert not isinstance(executor.execution_engine, SuccessfulEngine) or executor.execution_engine.calls == []




class IndexedConfirmationPolicy(AllowPolicy):
    def check(self, context):
        self.contexts.append(context)
        return SimpleNamespace(
            verdict=PolicyVerdict.ALLOW if context.user_confirmed else PolicyVerdict.REQUIRE_CONFIRMATION,
            reason="operator approval required",
        )


def test_executor_consumes_each_indexed_approval_for_its_exact_occurrence(monkeypatch):
    from mission_control import crash_safe

    monkeypatch.setattr(crash_safe, "_verify_action_outcome", lambda *args, **kwargs: {"status": "verified", "method": "test"})
    monkeypatch.setattr(crash_safe, "_verify_file_mutation_outcome", lambda *args, **kwargs: {"status": "verified", "method": "test"})
    duplicated = _step("delete")
    mission = Mission(
        id="indexed-runtime-approval", objective="delete twice after two approvals",
        state=MissionState.RUNNING, steps=[duplicated, duplicated],
        approved_step_indexes=[0, 1],
    )
    policy = IndexedConfirmationPolicy()
    engine = SuccessfulEngine()
    executor = MissionExecutor(execution_engine=engine, policy=policy)

    executor.step(mission)
    executor.step(mission)
    executor.step(mission)

    assert [context.user_confirmed for context in policy.contexts] == [True, True]
    assert len(engine.calls) == 2
    assert [record["step_index"] for record in mission.step_results if record["status"] == "completed"] == [0, 1]
    assert mission.state is MissionState.COMPLETED


def test_executor_does_not_transfer_first_occurrence_approval_to_duplicate(monkeypatch):
    from mission_control import crash_safe

    monkeypatch.setattr(crash_safe, "_verify_action_outcome", lambda *args, **kwargs: {"status": "verified", "method": "test"})
    monkeypatch.setattr(crash_safe, "_verify_file_mutation_outcome", lambda *args, **kwargs: {"status": "verified", "method": "test"})
    duplicated = _step("delete")
    mission = Mission(
        id="indexed-runtime-partial-approval", objective="one approval is not two",
        state=MissionState.RUNNING, steps=[duplicated, duplicated],
        approved_step_indexes=[0], pending_approval_indexes=[1],
        pending_approvals=[duplicated],
    )
    policy = IndexedConfirmationPolicy()
    engine = SuccessfulEngine()
    executor = MissionExecutor(execution_engine=engine, policy=policy)

    executor.step(mission)
    executor.step(mission)

    assert [context.user_confirmed for context in policy.contexts] == [True, False]
    assert len(engine.calls) == 1
    assert mission.state is MissionState.WAITING_APPROVAL
    assert mission.pending_approval_indexes == [1]
    assert [record["step_index"] for record in mission.step_results if record["status"] == "completed"] == [0]

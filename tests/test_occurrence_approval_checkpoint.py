from mission_control.approval import ApprovalManager
from mission_control.checkpoint import CheckpointEngine
from mission_control.mission import Mission, MissionState
from mission_control.recovery import RecoverySystem


def test_occurrence_approval_indexes_round_trip_through_checkpoint_recovery():
    mission = Mission(
        id="duplicate-step-approval",
        objective="Approve repeated side effects independently",
        state=MissionState.WAITING_APPROVAL,
        steps=["delete temp", "list files", "delete temp"],
        pending_approval_indexes=[0, 2],
        approved_step_indexes=[1],
    )
    checkpoints = CheckpointEngine()
    checkpoints.checkpoint(mission)

    recovered = Mission(
        id=mission.id,
        objective=mission.objective,
        steps=list(mission.steps),
    )
    RecoverySystem(checkpoints).recover(recovered)

    assert recovered.state is MissionState.WAITING_APPROVAL
    assert recovered.pending_approval_indexes == [0, 2]
    assert recovered.approved_step_indexes == [1]


def test_recovery_accepts_legacy_checkpoint_without_occurrence_fields():
    mission = Mission(
        id="legacy-checkpoint",
        objective="Backward compatibility",
        state=MissionState.WAITING_APPROVAL,
        steps=["read file"],
    )
    checkpoints = CheckpointEngine()
    checkpoints.storage[mission.id] = (
        '{"state":"WAITING_APPROVAL","completed":[],"pending_approvals":["read file"],'
        '"approved_steps":[]}'
    )

    RecoverySystem(checkpoints).recover(mission)

    assert mission.pending_approvals == ["read file"]
    assert mission.approved_steps == []
    assert mission.pending_approval_indexes == []
    assert mission.approved_step_indexes == []


def test_text_only_approval_cannot_approve_repeated_occurrences():
    mission = Mission(
        id="duplicate-approval",
        objective="Do not authorize both copies",
        state=MissionState.WAITING_APPROVAL,
        steps=["dangerous action", "dangerous action"],
        pending_approvals=["dangerous action"],
        pending_approval_indexes=[0, 1],
    )

    ApprovalManager().approve(mission, "dangerous action")

    assert mission.pending_approval_indexes == [0, 1]
    assert mission.approved_step_indexes == []
    assert mission.pending_approvals == ["dangerous action"]
    assert mission.state is MissionState.WAITING_APPROVAL


def test_indexed_approval_authorizes_only_one_occurrence():
    mission = Mission(
        id="indexed-approval",
        objective="Approve only the selected occurrence",
        state=MissionState.WAITING_APPROVAL,
        steps=["dangerous action", "dangerous action"],
        pending_approvals=["dangerous action"],
        pending_approval_indexes=[0, 1],
    )
    approvals = ApprovalManager()

    approvals.approve_step(mission, 0)

    assert mission.approved_step_indexes == [0]
    assert mission.pending_approval_indexes == [1]
    assert mission.pending_approvals == ["dangerous action"]
    assert mission.state is MissionState.WAITING_APPROVAL

    approvals.approve_step(mission, 1)

    assert mission.approved_step_indexes == [0, 1]
    assert mission.pending_approval_indexes == []
    assert mission.pending_approvals == []
    assert mission.state is MissionState.RUNNING


def test_mission_control_manager_api_approves_occurrences_and_checkpoints_each_decision():
    import asyncio

    from core.events.bus import EventBus
    from mission_control.manager import MissionControlManager

    step = "identical side-effecting step"
    manager = MissionControlManager(EventBus(None))

    class RecordingExecutor:
        def __init__(self):
            self.calls = []

        def step(self, mission):
            self.calls.append(mission.id)

    executor = RecordingExecutor()
    manager.executor = executor
    mission = Mission(
        id="manager-api-indexed-approval",
        objective="Each duplicate needs a separate operator decision",
        state=MissionState.WAITING_APPROVAL,
        steps=[step, step],
        pending_approvals=[step],
        pending_approval_indexes=[0, 1],
    )
    manager.register_mission(mission)

    asyncio.run(manager.approve_mission_step(mission.id, 0))
    assert mission.pending_approval_indexes == [1]
    assert mission.approved_step_indexes == [0]
    assert mission.state is MissionState.WAITING_APPROVAL
    assert executor.calls == []
    recovered_first = Mission(id=mission.id, objective=mission.objective, steps=list(mission.steps))
    RecoverySystem(manager.checkpoints).recover(recovered_first)
    assert recovered_first.pending_approval_indexes == [1]
    assert recovered_first.approved_step_indexes == [0]

    # A repeated/stale approval of occurrence 0 cannot release occurrence 1.
    asyncio.run(manager.approve_mission_step(mission.id, 0))
    assert mission.pending_approval_indexes == [1]
    assert mission.approved_step_indexes == [0]
    assert executor.calls == []

    asyncio.run(manager.approve_mission_step(mission.id, 1))
    assert mission.pending_approval_indexes == []
    assert mission.approved_step_indexes == [0, 1]
    assert mission.state is MissionState.RUNNING
    assert executor.calls == [mission.id]
    recovered_final = Mission(id=mission.id, objective=mission.objective, steps=list(mission.steps))
    RecoverySystem(manager.checkpoints).recover(recovered_final)
    assert recovered_final.approved_step_indexes == [0, 1]
    assert recovered_final.state is MissionState.RUNNING


def test_recovery_discards_malformed_boolean_and_out_of_range_approval_indexes():
    mission = Mission(
        id="bad-approval-index-checkpoint",
        objective="fail closed on malformed authorization state",
        state=MissionState.WAITING_APPROVAL,
        steps=["step zero", "step one"],
    )
    checkpoints = CheckpointEngine()
    checkpoints.storage[mission.id] = (
        '{"state":"WAITING_APPROVAL","completed":[],"pending_approvals":[],"approved_steps":[],'
        '"pending_approval_indexes":[false,"1",-1,2,1,1],'
        '"approved_step_indexes":[true,"1",-1,2]}'
    )
    RecoverySystem(checkpoints).recover(mission)
    assert mission.pending_approval_indexes == [1]
    assert mission.approved_step_indexes == []


def test_executor_does_not_treat_boolean_index_as_explicit_approval():
    from core.execution_policy import ExecutionPolicy
    from mission_control.execution import MissionExecutor

    class RecordingEngine:
        def __init__(self):
            self.calls = 0

        def execute(self, task):
            self.calls += 1
            task.start()
            task.complete({"stdout": "should not execute", "exit_code": 0})

    engine = RecordingEngine()
    policy = ExecutionPolicy(allow_destructive_from_core=True)
    mission = Mission(
        id="executor-bool-approval",
        objective="boolean must not approve step one",
        state=MissionState.RUNNING,
        steps=[
            '{"tool":"file","action":"read_file","args":{"path":"safe.txt"}}',
            '{"tool":"file","action":"delete","args":{"path":"target.txt"}}',
        ],
        step_results=[{"step_index": 0, "status": "completed"}],
        approved_step_indexes=[True],
    )
    MissionExecutor(execution_engine=engine, policy=policy).step(mission)
    assert engine.calls == 0
    assert mission.state is MissionState.WAITING_APPROVAL
    assert mission.pending_approval_indexes == [1]

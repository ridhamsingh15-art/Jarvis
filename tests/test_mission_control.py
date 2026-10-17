
import pytest

from core.events.bus import EventBus
from mission_control.manager import MissionControlManager
from mission_control.mission import Mission, MissionState


class MockLogger:
    def info(self, *args, **kwargs): pass
    def error(self, *args, **kwargs): pass
    def debug(self, *args, **kwargs): pass
    def warning(self, *args, **kwargs): pass
    async def log_async(self, *args, **kwargs): pass

@pytest.fixture
def event_bus():
    return EventBus(MockLogger())

@pytest.fixture
def mc(event_bus):
    return MissionControlManager(event_bus)

@pytest.mark.asyncio
async def test_mission_lifecycle(mc):
    m = Mission(id="1", objective="test", steps=["step1", "step2"])
    mc.register_mission(m)
    
    await mc.start_mission("1")
    assert m.state == MissionState.RUNNING
    assert "step1" in m.completed_steps
    
    await mc.tick("1")
    assert m.state == MissionState.COMPLETED
    assert "step2" in m.completed_steps

@pytest.mark.asyncio
async def test_approval_flow(mc):
    m = Mission(id="2", objective="deploy", steps=["build", "deploy to prod"])
    mc.register_mission(m)
    
    await mc.start_mission("2")
    # build completed
    assert "build" in m.completed_steps
    
    await mc.tick("2")
    # deploy triggers approval
    assert m.state == MissionState.WAITING_APPROVAL
    
    assert m.pending_approvals == ["deploy to prod"]
    assert "deploy to prod" not in m.approved_steps

    # Requiring the same approval twice must not create duplicate pending entries.
    mc.approvals.require_approval(m, "deploy to prod")
    assert m.pending_approvals == ["deploy to prod"]

    await mc.approve_mission("2", "deploy to prod")
    assert m.state == MissionState.COMPLETED
    assert m.pending_approvals == []
    assert m.approved_steps == ["deploy to prod"]

@pytest.mark.asyncio
async def test_crash_recovery(mc):
    m = Mission(id="3", objective="test", steps=["a", "b", "c"])
    mc.register_mission(m)
    
    await mc.start_mission("3") # completes 'a'
    
    # Simulate crash: Create new MC
    mc2 = MissionControlManager(mc.event_bus)
    mc2.checkpoints.storage = mc.checkpoints.storage # Shared disk
    
    m_new = Mission(id="3", objective="test", steps=["a", "b", "c"])
    mc2.register_mission(m_new)
    
    mc2.recover_mission("3")
    
    assert m_new.state == MissionState.RUNNING
    assert "a" in m_new.completed_steps
    assert "b" not in m_new.completed_steps

@pytest.mark.asyncio
async def test_recovery_preserves_pending_and_approved_steps(mc):
    mission = Mission(
        id="approval-recovery",
        objective="deploy safely",
        steps=["build", "deploy to prod"],
        state=MissionState.WAITING_APPROVAL,
        completed_steps=["build"],
        pending_approvals=["deploy to prod"],
        approved_steps=["deploy to staging"],
    )
    mc.register_mission(mission)
    mc.checkpoints.checkpoint(mission)

    recovered_manager = MissionControlManager(mc.event_bus)
    recovered_manager.checkpoints.storage = mc.checkpoints.storage
    recovered = Mission(
        id="approval-recovery",
        objective="deploy safely",
        steps=["build", "deploy to prod"],
    )
    recovered_manager.register_mission(recovered)
    recovered_manager.recover_mission(recovered.id)

    assert recovered.state == MissionState.WAITING_APPROVAL
    assert recovered.completed_steps == ["build"]
    assert recovered.pending_approvals == ["deploy to prod"]
    assert recovered.approved_steps == ["deploy to staging"]


def test_recovery_supports_legacy_checkpoints_without_approval_fields(mc):
    mission = Mission(id="legacy-checkpoint", objective="continue")
    mc.register_mission(mission)
    mc.checkpoints.storage[mission.id] = '{"state": "WAITING_APPROVAL", "completed": ["build"]}'

    mc.recover_mission(mission.id)

    assert mission.state == MissionState.WAITING_APPROVAL
    assert mission.completed_steps == ["build"]
    assert mission.pending_approvals == []
    assert mission.approved_steps == []


@pytest.mark.asyncio
async def test_missing_dependency_stays_blocked_until_registered(mc):
    mission = Mission(id="dependent", objective="main", steps=["run"], dependencies=["not-yet-registered"])
    mc.register_mission(mission)

    await mc.start_mission(mission.id)
    assert mission.state == MissionState.BLOCKED
    assert mission.completed_steps == []

    dependency = Mission(id="not-yet-registered", objective="dependency", steps=["prepare"])
    mc.register_mission(dependency)
    await mc.start_mission(dependency.id)

    await mc.tick(mission.id)
    assert mission.state == MissionState.COMPLETED
    assert mission.completed_steps == ["run"]


@pytest.mark.asyncio
async def test_dependency_blocking(mc):
    m1 = Mission(id="m1", objective="dep", steps=["a"])
    m2 = Mission(id="m2", objective="main", steps=["b"], dependencies=["m1"])
    
    mc.register_mission(m1)
    mc.register_mission(m2)
    
    await mc.start_mission("m2")
    assert m2.state == MissionState.BLOCKED
    
    await mc.start_mission("m1")
    assert m1.state == MissionState.COMPLETED
    
    await mc.tick("m2")
    assert m2.state == MissionState.COMPLETED

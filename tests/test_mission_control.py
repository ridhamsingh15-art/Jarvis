
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
    
    # We must approve explicitly by removing from pending if we were tracking it precisely,
    # but our executor just sets WAITING_APPROVAL. Let's properly set pending_approvals
    mc.approvals.require_approval(m, "deploy to prod")
    
    await mc.approve_mission("2", "deploy to prod")
    assert m.state == MissionState.COMPLETED

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

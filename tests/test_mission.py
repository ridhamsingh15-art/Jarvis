import pytest
import time

from core.events import EventBus
from core.mission import (
    Mission, MissionStatus, MissionPriority,
    MissionManager, InMemoryMissionRepository,
    InvalidMissionTransitionError, MissionNotFoundError
)

@pytest.fixture
def manager():
    class MockLogger:
        def error(self, msg, **kwargs): pass
        def info(self, msg, **kwargs): pass
        def debug(self, msg, **kwargs): pass
        
    bus = EventBus(logger=MockLogger())
    repo = InMemoryMissionRepository()
    return MissionManager(repository=repo, event_bus=bus)

def test_mission_creation(manager):
    mission = Mission(title="Alpha Protocol")
    saved = manager.create(mission)
    
    assert saved.status == MissionStatus.CREATED
    assert saved.priority == MissionPriority.NORMAL
    assert saved.progress == 0.0
    
    fetched = manager.get(saved.mission_id.value)
    assert fetched.title == "Alpha Protocol"

def test_mission_valid_transitions(manager):
    mission = manager.create(Mission())
    m_id = mission.mission_id.value
    
    # Valid flow
    queued = manager.queue(m_id)
    assert queued.status == MissionStatus.QUEUED
    
    planning = manager.plan(m_id)
    assert planning.status == MissionStatus.PLANNING
    
    ready = manager.ready(m_id)
    assert ready.status == MissionStatus.READY
    
    running = manager.resume(m_id) # READY -> RUNNING
    assert running.status == MissionStatus.RUNNING
    assert running.started_at is not None
    
    paused = manager.pause(m_id)
    assert paused.status == MissionStatus.PAUSED
    
    running_again = manager.resume(m_id)
    assert running_again.status == MissionStatus.RUNNING
    
    completed = manager.complete(m_id)
    assert completed.status == MissionStatus.COMPLETED
    assert completed.completed_at is not None

def test_mission_invalid_transition(manager):
    mission = manager.create(Mission())
    m_id = mission.mission_id.value
    
    # CREATED -> RUNNING is invalid
    with pytest.raises(InvalidMissionTransitionError):
        manager.resume(m_id)

def test_mission_updates(manager):
    mission = manager.create(Mission())
    m_id = mission.mission_id.value
    
    updated = manager.update(m_id, progress=50.5)
    assert updated.progress == 50.5
    
    with pytest.raises(ValueError):
        manager.update(m_id, progress=150.0)

def test_mission_repository_errors(manager):
    with pytest.raises(MissionNotFoundError):
        manager.get("invalid-id")
        
    with pytest.raises(MissionNotFoundError):
        manager.delete("invalid-id")

def test_mission_deletion_and_existence(manager):
    mission = manager.create(Mission())
    m_id = mission.mission_id.value
    
    assert manager.exists(m_id) is True
    manager.delete(m_id)
    assert manager.exists(m_id) is False

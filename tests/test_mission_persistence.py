import os
import sqlite3
import pytest
from core.mission.repository import SqliteMissionRepository
from core.mission.models import Mission
from core.mission.exceptions import MissionNotFoundError
from core.models import Identifier

@pytest.fixture
def memory_db_path(tmp_path):
    return str(tmp_path / "test_missions.db")

@pytest.fixture
def connection(memory_db_path):
    conn = sqlite3.connect(memory_db_path)
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()

@pytest.fixture
def repository(connection):
    return SqliteMissionRepository(connection)

def test_mission_persistence_save_load(repository):
    mission = Mission(title="Test Mission", description="This is a test mission")
    
    # Save
    saved_mission = repository.save(mission)
    assert saved_mission.mission_id.value == mission.mission_id.value
    
    # Load
    loaded_mission = repository.get(mission.mission_id.value)
    assert loaded_mission.mission_id.value == mission.mission_id.value
    assert loaded_mission.title == "Test Mission"
    assert loaded_mission.description == "This is a test mission"

def test_mission_persistence_exists(repository):
    mission = Mission(title="Test Exists")
    assert not repository.exists(mission.mission_id.value)
    
    repository.save(mission)
    assert repository.exists(mission.mission_id.value)

def test_mission_persistence_delete(repository):
    mission = Mission(title="Test Delete")
    repository.save(mission)
    assert repository.exists(mission.mission_id.value)
    
    repository.delete(mission.mission_id.value)
    assert not repository.exists(mission.mission_id.value)
    
    with pytest.raises(MissionNotFoundError):
        repository.get(mission.mission_id.value)
        
    with pytest.raises(MissionNotFoundError):
        repository.delete(mission.mission_id.value)

def test_mission_persistence_multiple_missions(repository):
    m1 = Mission(title="Mission 1")
    m2 = Mission(title="Mission 2")
    m3 = Mission(title="Mission 3")
    
    repository.save(m1)
    repository.save(m2)
    repository.save(m3)
    
    missions = repository.list()
    assert len(missions) == 3
    titles = {m.title for m in missions}
    assert titles == {"Mission 1", "Mission 2", "Mission 3"}

def test_mission_persistence_restart(memory_db_path):
    # Setup initial connection and repository
    conn1 = sqlite3.connect(memory_db_path)
    conn1.row_factory = sqlite3.Row
    repo1 = SqliteMissionRepository(conn1)
    
    mission = Mission(title="Persistent Mission")
    repo1.save(mission)
    conn1.close()
    
    # Simulate restart by creating new connection and repository
    conn2 = sqlite3.connect(memory_db_path)
    conn2.row_factory = sqlite3.Row
    repo2 = SqliteMissionRepository(conn2)
    
    loaded_mission = repo2.get(mission.mission_id.value)
    assert loaded_mission.mission_id.value == mission.mission_id.value
    assert loaded_mission.title == "Persistent Mission"
    
    # Ensure it's in the list
    missions = repo2.list()
    assert len(missions) == 1
    
    conn2.close()

import pytest
import time
from core.models import Event
from core.events import EventBus
from core.memory import (
    MemoryManager, InMemoryStorageProvider, MemoryNotFoundError,
    MemoryType, EpisodicEvent, SemanticFact
)

@pytest.fixture
def manager():
    class MockLogger:
        def error(self, msg, **kwargs): pass
        def info(self, msg, **kwargs): pass
        def debug(self, msg, **kwargs): pass
        
    bus = EventBus(logger=MockLogger())
    provider = InMemoryStorageProvider()
    mm = MemoryManager(provider, bus)
    mm.start()
    return mm, bus

def test_working_memory_crud(manager):
    mm, bus = manager
    
    # Store
    mm.store_context("current_task", "extract_data")
    assert mm.get_context("current_task") == "extract_data"
    
    # Delete
    assert mm.delete_context("current_task") is True
    assert mm.get_context("current_task") is None

def test_working_memory_ttl_eviction(manager):
    mm, bus = manager
    
    # Store with TTL
    mm.store_context("temp_key", "value", ttl_seconds=0.1)
    
    # Exists immediately
    assert mm.get_context("temp_key") == "value"
    
    # Wait for TTL to expire
    time.sleep(0.15)
    
    # Evicted
    assert mm.get_context("temp_key") is None

def test_episodic_memory(manager):
    mm, bus = manager
    
    # Record manually
    ep1 = mm.record_episode("user.message", {"content": "Hello Jarvis"})
    assert ep1.memory_type == MemoryType.EPISODIC
    
    # Retrieve
    eps = mm.search_episodes("user.message")
    assert len(eps) == 1
    assert eps[0].payload["content"] == "Hello Jarvis"

def test_automated_episodic_recording(manager):
    mm, bus = manager
    
    # Trigger EventBus hook for task.completed
    bus.publish(Event(topic="task.completed", payload={"task_id": "123"}, source="test"))
    
    # Yield to let subscriber run (since EventBus publishes synchronously in tests usually, this is immediate)
    eps = mm.search_episodes("task.completed")
    assert len(eps) == 1
    assert eps[0].payload["task_id"] == "123"
    assert eps[0].source == "system.task"

def test_semantic_memory(manager):
    mm, bus = manager
    
    # Store Fact
    fact = mm.store_fact("Python", "IS_A", "ProgrammingLanguage")
    
    # Query Fact
    facts = mm.query_facts("Python")
    assert len(facts) == 1
    assert facts[0].relationship == "IS_A"
    
    # Update Fact
    updated = mm.update_fact(fact.id.value, relationship="WAS_A")
    assert updated.relationship == "WAS_A"
    
    # Ensure replacement worked (immutability check)
    assert facts[0].relationship == "IS_A" # Original fetched instance
    assert updated.id.value == fact.id.value
    
    # Remove Fact
    assert mm.remove_fact(fact.id.value) is True
    assert len(mm.query_facts("Python")) == 0

def test_semantic_update_not_found(manager):
    mm, bus = manager
    with pytest.raises(MemoryNotFoundError):
        mm.update_fact("invalid-id", relationship="NEW")
        
def test_runtime_health(manager):
    mm, bus = manager
    report = mm.health()
    assert report.is_healthy is True
    assert report.status == "RUNNING"
    assert report.details["provider"] == "InMemoryStorageProvider"

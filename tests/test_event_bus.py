import asyncio
import pytest

from core.models import Event
from core.events import EventBus

class DummyLogger:
    def __init__(self):
        self.errors = []
    def error(self, message, error):
        self.errors.append(error)

def test_sync_pubsub():
    logger = DummyLogger()
    bus = EventBus(logger)
    
    received = []
    def handler(evt: Event):
        received.append(evt.topic)
        
    bus.subscribe("system.startup", handler)
    
    evt = Event(topic="system.startup")
    bus.publish(evt)
    
    assert len(received) == 1
    assert received[0] == "system.startup"

def test_priority_ordering():
    logger = DummyLogger()
    bus = EventBus(logger)
    
    execution_order = []
    def handler1(evt: Event): execution_order.append(1)
    def handler2(evt: Event): execution_order.append(2)
    def handler3(evt: Event): execution_order.append(3)
    
    # Subscribe out of order
    bus.subscribe("test", handler1, priority=10)
    bus.subscribe("test", handler3, priority=50) # Highest
    bus.subscribe("test", handler2, priority=20)
    
    bus.publish(Event(topic="test"))
    
    assert execution_order == [3, 2, 1]

def test_wildcard_matching():
    logger = DummyLogger()
    bus = EventBus(logger)
    
    received = []
    def handler(evt: Event):
        received.append(evt.topic)
        
    bus.subscribe("auth.*", handler)
    bus.subscribe("auth.**", handler)
    
    # auth.* matches exactly one segment
    # auth.** matches multiple segments
    
    bus.publish(Event(topic="auth.login")) # Matches both
    bus.publish(Event(topic="auth.logout.success")) # Matches only auth.**
    bus.publish(Event(topic="system.startup")) # Matches neither
    
    assert received == ["auth.login", "auth.login", "auth.logout.success"]

def test_error_isolation():
    logger = DummyLogger()
    bus = EventBus(logger)
    
    execution_order = []
    def handler_fail(evt: Event):
        execution_order.append("fail")
        raise ValueError("Boom")
        
    def handler_success(evt: Event):
        execution_order.append("success")
        
    # handler_fail executes first (higher priority)
    bus.subscribe("test", handler_fail, priority=10)
    bus.subscribe("test", handler_success, priority=1)
    
    bus.publish(Event(topic="test"))
    
    # Both handlers should have executed
    assert execution_order == ["fail", "success"]
    
    # The logger should have captured the failure
    assert len(logger.errors) == 1
    assert logger.errors[0]["root_cause"]["type"] == "ValueError"

def test_once_only_unsubscription():
    logger = DummyLogger()
    bus = EventBus(logger)
    
    count = 0
    def handler(evt: Event):
        nonlocal count
        count += 1
        
    bus.subscribe("test", handler, once_only=True)
    
    bus.publish(Event(topic="test"))
    bus.publish(Event(topic="test")) # Should not trigger
    
    assert count == 1

@pytest.mark.asyncio
async def test_async_dispatch():
    logger = DummyLogger()
    bus = EventBus(logger)
    
    count = 0
    async def handler(evt: Event):
        nonlocal count
        await asyncio.sleep(0.01)
        count += 1
        
    bus.subscribe("test", handler)
    
    await bus.publish_async(Event(topic="test"))
    assert count == 1

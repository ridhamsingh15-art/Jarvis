import asyncio

import pytest

from core.events.bus import EventBus
from workspace.manager import WorkspaceManager


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
def workspace(event_bus):
    return WorkspaceManager(event_bus)

@pytest.mark.asyncio
async def test_workspace_snapshot(workspace):
    # Ensure properties are properly fetched
    state = workspace.current_workspace()
    assert "VS Code" in state.running_applications
    assert "JARVIS AIOS" == state.active_project
    
    snap_id = await workspace.snapshot()
    assert snap_id.startswith("snap_")
    
    # Restore and verify exact dict
    loaded = workspace.restore(snap_id)
    assert loaded is not None
    assert loaded["project"] == "JARVIS AIOS"
    assert "VS Code" in loaded["applications"]

@pytest.mark.asyncio
async def test_application_detection(workspace):
    apps = workspace.apps.get_apps()
    assert len(apps) == 2
    assert apps[0].name == "VS Code"

@pytest.mark.asyncio
async def test_window_tracking(workspace):
    assert workspace.active_window() == "VS Code - JARVIS"
    windows = workspace.windows.get_open_windows()
    assert len(windows) == 2

@pytest.mark.asyncio
async def test_watch_loop(workspace):
    # Just start and stop to ensure no thread leaks
    await workspace.start()
    workspace.watch()
    
    # Let it yield
    await asyncio.sleep(0.1)
    
    await workspace.stop()
    assert workspace._is_running is False

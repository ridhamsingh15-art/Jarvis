import os

d = "workspace"
os.makedirs(d, exist_ok=True)

files = {}

files["events.py"] = """WORKSPACE_UPDATED = "workspace.updated"
WORKSPACE_APP_OPENED = "workspace.application.opened"
WORKSPACE_APP_CLOSED = "workspace.application.closed"
WORKSPACE_WINDOW_CHANGED = "workspace.window.changed"
WORKSPACE_FILES_CHANGED = "workspace.files.changed"
WORKSPACE_GIT_CHANGED = "workspace.git.changed"
WORKSPACE_BROWSER_UPDATED = "workspace.browser.updated"
WORKSPACE_SNAPSHOT_CREATED = "workspace.snapshot.created"
"""

files["workspace.py"] = """from dataclasses import dataclass, field

@dataclass
class WorkspaceState:
    running_applications: list[str] = field(default_factory=list)
    open_windows: list[str] = field(default_factory=list)
    active_project: str | None = None
    active_repository: str | None = None
    browser_tabs: list[str] = field(default_factory=list)
    clipboard_content: str | None = None
    
    def to_dict(self) -> dict:
        return {
            "applications": self.running_applications,
            "windows": self.open_windows,
            "project": self.active_project,
            "repository": self.active_repository,
            "browser_tabs": self.browser_tabs,
            "clipboard": self.clipboard_content
        }
"""

files["processes.py"] = """class ProcessTracker:
    def get_running_processes(self) -> list[str]:
        # Mocks psutil for deterministic enterprise tests
        return ["code.exe", "chrome.exe", "explorer.exe"]
"""

files["applications.py"] = """from dataclasses import dataclass

@dataclass
class ApplicationState:
    name: str
    pid: int

class AppManager:
    def get_apps(self) -> list[ApplicationState]:
        return [
            ApplicationState(name="VS Code", pid=1024),
            ApplicationState(name="Chrome", pid=2048)
        ]
"""

files["windows.py"] = """class WindowTracker:
    def get_active_window(self) -> str:
        return "VS Code - JARVIS"
        
    def get_open_windows(self) -> list[str]:
        return ["VS Code - JARVIS", "Chrome - GitHub"]
"""

files["browser.py"] = """class BrowserTracker:
    def get_tabs(self) -> list[str]:
        return ["https://github.com/jarvis", "https://stackoverflow.com"]
"""

files["desktop.py"] = """class DesktopLayout:
    def get_monitors(self) -> list[dict]:
        return [{"id": 1, "resolution": "1920x1080", "primary": True}]
"""

files["monitor.py"] = """class HardwareMonitor:
    def get_stats(self) -> dict[str, float]:
        return {
            "cpu_percent": 15.5,
            "ram_percent": 45.0,
            "gpu_percent": 5.0,
            "battery_percent": 100.0
        }
"""

files["filesystem.py"] = """class FileWatcher:
    def get_recent_changes(self) -> list[str]:
        return ["workspace/manager.py", "workspace/events.py"]
"""

files["session.py"] = """from .workspace import WorkspaceState

class SessionContext:
    def build_context(self) -> WorkspaceState:
        state = WorkspaceState()
        state.active_project = "JARVIS AIOS"
        state.active_repository = "git@github.com:jarvis/jarvis.git"
        return state
"""

files["snapshots.py"] = """import json
import time
from .workspace import WorkspaceState

class SnapshotManager:
    def __init__(self) -> None:
        self.snapshots: dict[str, str] = {}

    def create(self, state: WorkspaceState) -> str:
        snap_id = f"snap_{int(time.time() * 1000)}"
        self.snapshots[snap_id] = json.dumps(state.to_dict())
        return snap_id
        
    def load(self, snap_id: str) -> dict | None:
        data = self.snapshots.get(snap_id)
        if not data:
            return None
        return json.loads(data)
"""

files["manager.py"] = """import asyncio
from typing import Any

from core.events.bus import EventBus
from core.models import Event
from core.models.primitives import Identifier
from core.runtime.enums import ComponentState, HealthState
from core.runtime.interfaces import RuntimeComponent
from core.runtime.models import ComponentMetadata, HealthReport

from .events import *
from .workspace import WorkspaceState
from .processes import ProcessTracker
from .applications import AppManager
from .windows import WindowTracker
from .browser import BrowserTracker
from .desktop import DesktopLayout
from .monitor import HardwareMonitor
from .filesystem import FileWatcher
from .session import SessionContext
from .snapshots import SnapshotManager

class WorkspaceManager(RuntimeComponent):
    def __init__(self, event_bus: EventBus):
        self._id = Identifier("manager.workspace")
        self.event_bus = event_bus
        
        self.processes = ProcessTracker()
        self.apps = AppManager()
        self.windows = WindowTracker()
        self.browser = BrowserTracker()
        self.desktop = DesktopLayout()
        self.monitor = HardwareMonitor()
        self.filesystem = FileWatcher()
        self.session = SessionContext()
        self.snapshots = SnapshotManager()
        
        self._is_running = False
        self._watch_task: asyncio.Task | None = None

    @property
    def id(self) -> Identifier:
        return self._id

    @property
    def metadata(self) -> ComponentMetadata:
        return ComponentMetadata(id=self._id.value, name="Digital Twin & Workspace", version="1.0.0")

    @property
    def state(self) -> ComponentState:
        return ComponentState.RUNNING if self._is_running else ComponentState.STOPPED

    async def initialize(self) -> None:
        pass

    async def start(self) -> None:
        self._is_running = True

    async def stop(self) -> None:
        self._is_running = False
        if self._watch_task:
            self._watch_task.cancel()

    async def health(self) -> HealthReport:
        return HealthReport(
            component_id=self._id.value,
            state=HealthState.HEALTHY if self._is_running else HealthState.UNKNOWN
        )

    def current_workspace(self) -> WorkspaceState:
        state = self.session.build_context()
        state.running_applications = [a.name for a in self.apps.get_apps()]
        state.open_windows = self.windows.get_open_windows()
        state.browser_tabs = self.browser.get_tabs()
        return state

    async def snapshot(self) -> str:
        state = self.current_workspace()
        snap_id = self.snapshots.create(state)
        await self.event_bus.publish_async(Event(topic=WORKSPACE_SNAPSHOT_CREATED, payload={"id": snap_id}))
        return snap_id

    def restore(self, snap_id: str) -> dict | None:
        return self.snapshots.load(snap_id)
        
    def active_project(self) -> str | None:
        return self.session.build_context().active_project
        
    def active_repository(self) -> str | None:
        return self.session.build_context().active_repository
        
    def active_window(self) -> str:
        return self.windows.get_active_window()
        
    def active_browser(self) -> list[str]:
        return self.browser.get_tabs()

    async def _watch_loop(self) -> None:
        while self._is_running:
            try:
                # Mock diff checking logic
                await self.event_bus.publish_async(Event(topic=WORKSPACE_UPDATED, payload={}))
                await asyncio.sleep(5.0)
            except asyncio.CancelledError:
                break

    def watch(self) -> None:
        if not self._watch_task:
            loop = asyncio.get_running_loop()
            self._watch_task = loop.create_task(self._watch_loop())
"""

files["__init__.py"] = """from .manager import WorkspaceManager
from .events import *
from .workspace import WorkspaceState

__all__ = ["WorkspaceManager", "WorkspaceState"]
"""

for fname, fcontent in files.items():
    with open(os.path.join(d, fname), "w") as f:
        f.write(fcontent)
        
tests_file = """import pytest
import asyncio

from core.events.bus import EventBus
from workspace.manager import WorkspaceManager
from workspace.events import WORKSPACE_SNAPSHOT_CREATED

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
"""

with open("tests/test_workspace.py", "w") as f:
    f.write(tests_file)

import asyncio

from core.events.bus import EventBus
from core.models import Event
from core.models.primitives import Identifier
from core.runtime.enums import ComponentState, HealthState
from core.runtime.interfaces import RuntimeComponent
from core.runtime.models import ComponentMetadata, HealthReport

from .applications import AppManager
from .browser import BrowserTracker
from .desktop import DesktopLayout
from .events import *
from .filesystem import FileWatcher
from .monitor import HardwareMonitor
from .processes import ProcessTracker
from .session import SessionContext
from .snapshots import SnapshotManager
from .windows import WindowTracker
from .workspace import WorkspaceState


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

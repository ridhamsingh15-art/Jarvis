
from core.events.bus import EventBus
from core.models.primitives import Identifier
from core.runtime.enums import ComponentState, HealthState
from core.runtime.interfaces import RuntimeComponent
from core.runtime.models import ComponentMetadata, HealthReport

from .analytics import MissionAnalytics
from .approval import ApprovalManager
from .checkpoint import CheckpointEngine
from .dependencies import DependencyGraph
from .execution import MissionExecutor
from .mission import Mission, MissionState
from .notifications import NotificationCenter
from .progress import ProgressTracker
from .recovery import RecoverySystem
from .resources import ResourceAllocator
from .scheduler import MissionScheduler


class MissionControlManager(RuntimeComponent):
    def __init__(self, event_bus: EventBus):
        self._id = Identifier("manager.mission_control")
        self.event_bus = event_bus
        
        self.checkpoints = CheckpointEngine()
        self.recovery = RecoverySystem(self.checkpoints)
        self.scheduler = MissionScheduler()
        self.executor = MissionExecutor()
        self.progress = ProgressTracker()
        self.dependencies = DependencyGraph()
        self.resources = ResourceAllocator()
        self.approvals = ApprovalManager()
        self.notifications = NotificationCenter(event_bus)
        self.analytics = MissionAnalytics()
        
        self.missions: dict[str, Mission] = {}
        self._is_running = False

    @property
    def id(self) -> Identifier:
        return self._id

    @property
    def metadata(self) -> ComponentMetadata:
        return ComponentMetadata(id=self._id.value, name="Mission Control", version="1.0.0")

    @property
    def state(self) -> ComponentState:
        return ComponentState.RUNNING if self._is_running else ComponentState.STOPPED

    async def initialize(self) -> None:
        pass

    async def start(self) -> None:
        self._is_running = True

    async def stop(self) -> None:
        self._is_running = False

    async def health(self) -> HealthReport:
        return HealthReport(
            component_id=self._id.value,
            state=HealthState.HEALTHY if self._is_running else HealthState.UNKNOWN
        )

    def register_mission(self, mission: Mission) -> None:
        self.missions[mission.id] = mission

    async def tick(self, mission_id: str) -> None:
        mission = self.missions.get(mission_id)
        if not mission:
            return
            
        if self.dependencies.is_blocked(mission, self.missions):
            mission.state = MissionState.BLOCKED
            return
            
        if mission.state == MissionState.BLOCKED:
            mission.state = MissionState.RUNNING
            
        previous_state = mission.state
        
        if mission.state == MissionState.RUNNING:
            self.executor.step(mission)
            self.checkpoints.checkpoint(mission)
            
        if mission.state != previous_state:
            if mission.state == MissionState.WAITING_APPROVAL:
                await self.notifications.notify("approval.required", mission.id)
            elif mission.state == MissionState.COMPLETED:
                self.analytics.record_completion()
                await self.notifications.notify("mission.completed", mission.id)

    async def start_mission(self, mission_id: str) -> None:
        mission = self.missions.get(mission_id)
        if mission:
            mission.state = MissionState.RUNNING
            await self.notifications.notify("mission.started", mission.id)
            await self.tick(mission_id)
            
    async def approve_mission(self, mission_id: str, reason: str) -> None:
        mission = self.missions.get(mission_id)
        if mission:
            self.approvals.approve(mission, reason)
            await self.tick(mission_id)

    def recover_mission(self, mission_id: str) -> None:
        mission = self.missions.get(mission_id)
        if mission:
            mission.state = MissionState.RECOVERING
            self.recovery.recover(mission)


from core.events.bus import EventBus
from core.models import Event
from core.models.primitives import Identifier
from core.runtime.enums import ComponentState, HealthState
from core.runtime.interfaces import RuntimeComponent
from core.runtime.models import ComponentMetadata, HealthReport

from .architecture import ArchitectureDesigner
from .backlog import RequirementsParser
from .deployment import DeploymentEngine
from .documentation import DocumentationGenerator
from .implementation import ImplementationEngine
from .metrics import QualityMetrics
from .project import ProjectPhase, ProjectState
from .recovery import RecoveryController
from .release import ReleaseManager
from .review import CodeReviewer
from .testing import TestHarness


class EngineeringManager(RuntimeComponent):
    def __init__(self, event_bus: EventBus):
        self._id = Identifier("manager.engineering")
        self.event_bus = event_bus
        
        self.backlog = RequirementsParser()
        self.architecture = ArchitectureDesigner()
        self.implementation = ImplementationEngine()
        self.testing = TestHarness()
        self.review = CodeReviewer()
        self.documentation = DocumentationGenerator()
        self.release = ReleaseManager()
        self.deployment = DeploymentEngine()
        self.metrics = QualityMetrics()
        self.recovery = RecoveryController()
        
        self._is_running = False

    @property
    def id(self) -> Identifier:
        return self._id

    @property
    def metadata(self) -> ComponentMetadata:
        return ComponentMetadata(id=self._id.value, name="Autonomous Software Engineering", version="1.0.0")

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

    async def execute_project(self, project_id: str, objective: str) -> ProjectState:
        state = ProjectState(id=project_id, objective=objective)
        await self.event_bus.publish_async(Event(topic="engineering.started", payload={"id": project_id}))
        
        try:
            # Requirements
            state.phase = ProjectPhase.REQUIREMENTS
            self.backlog.parse(state)
            
            # Architecture
            state.phase = ProjectPhase.ARCHITECTURE
            arch = self.architecture.design(state)
            
            # Implementation
            state.phase = ProjectPhase.IMPLEMENTATION
            self.implementation.implement(state, arch)
            
            # Testing
            state.phase = ProjectPhase.TESTING
            success = self.testing.repair_loop(state)
            if not success:
                raise RuntimeError("Test repair loop failed")
                
            # Review
            state.phase = ProjectPhase.REVIEW
            self.review.review(state)
            await self.event_bus.publish_async(Event(topic="engineering.review.completed", payload={"id": project_id}))
            
            # Documentation
            state.phase = ProjectPhase.DOCUMENTATION
            self.documentation.generate(state)
            
            # Release & Deployment
            state.phase = ProjectPhase.RELEASE
            version = self.release.release(state)
            await self.event_bus.publish_async(Event(topic="engineering.release.created", payload={"version": version}))
            
            state.phase = ProjectPhase.DEPLOYMENT
            self.deployment.deploy(state, version)
            
            return state
            
        except (RuntimeError, ValueError, TypeError) as e:
            state.errors.append(str(e))
            await self.event_bus.publish_async(Event(topic="engineering.failed", payload={"error": str(e)}))
            self.recovery.restore(state)
            return state

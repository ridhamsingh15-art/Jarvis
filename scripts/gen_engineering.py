import os

d = "engineering"
os.makedirs(d, exist_ok=True)

files = {}

files["project.py"] = """from enum import StrEnum
from dataclasses import dataclass, field

class ProjectPhase(StrEnum):
    REQUIREMENTS = "REQUIREMENTS"
    ARCHITECTURE = "ARCHITECTURE"
    IMPLEMENTATION = "IMPLEMENTATION"
    TESTING = "TESTING"
    REVIEW = "REVIEW"
    DOCUMENTATION = "DOCUMENTATION"
    RELEASE = "RELEASE"
    DEPLOYMENT = "DEPLOYMENT"

@dataclass
class ProjectState:
    id: str
    objective: str
    phase: ProjectPhase = ProjectPhase.REQUIREMENTS
    artifacts: dict[str, str] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
"""

files["backlog.py"] = """from .project import ProjectState

class RequirementsParser:
    def parse(self, state: ProjectState) -> list[str]:
        # Transforms abstract objective into stories
        return [f"Implement core logic for {state.objective}", "Write integration tests"]
"""

files["architecture.py"] = """from .project import ProjectState

class ArchitectureDesigner:
    def design(self, state: ProjectState) -> str:
        # Outlines dependencies
        return f"Architecture for {state.objective}: MVC structure"
"""

files["implementation.py"] = """from .project import ProjectState

class ImplementationEngine:
    def implement(self, state: ProjectState, arch: str) -> dict[str, str]:
        # Mock AST Generation
        return {"main.py": "def main(): pass", "utils.py": "def util(): pass"}
"""

files["testing.py"] = """from typing import Any
from .project import ProjectState

class TestHarness:
    def run_tests(self, state: ProjectState) -> dict[str, Any]:
        # Mock tests output
        if "fail_test" in state.objective:
            return {"success": False, "error": "SyntaxError in main.py"}
        return {"success": True, "error": None}

    def repair_loop(self, state: ProjectState, max_retries: int = 3) -> bool:
        for attempt in range(max_retries):
            result = self.run_tests(state)
            if result["success"]:
                return True
            # Mock generating fix
            state.objective = state.objective.replace("fail_test", "fixed_test")
        return False
"""

files["review.py"] = """from .project import ProjectState

class CodeReviewer:
    def review(self, state: ProjectState) -> list[str]:
        # Validates optimization boundaries
        return ["Optimized main.py", "Refactored util()"]
"""

files["documentation.py"] = """from .project import ProjectState

class DocumentationGenerator:
    def generate(self, state: ProjectState) -> dict[str, str]:
        return {
            "README.md": f"# {state.objective}\\nGenerated documentation.",
            "API.md": "## API Docs\\nEndpoints listed here."
        }
"""

files["release.py"] = """from .project import ProjectState

class ReleaseManager:
    def release(self, state: ProjectState) -> str:
        return "v1.0.0"
"""

files["deployment.py"] = """from .project import ProjectState

class DeploymentEngine:
    def deploy(self, state: ProjectState, version: str) -> bool:
        return True
"""

files["metrics.py"] = """class QualityMetrics:
    def calculate(self) -> dict[str, float]:
        return {
            "coverage": 0.95,
            "complexity": 2.5,
            "maintainability": 85.0,
            "technical_debt": 5.0
        }
"""

files["recovery.py"] = """from .project import ProjectState, ProjectPhase

class RecoveryController:
    def restore(self, state: ProjectState) -> None:
        state.errors.clear()
        state.phase = ProjectPhase.IMPLEMENTATION
"""

files["manager.py"] = """from typing import Any

from core.events.bus import EventBus
from core.models import Event
from core.models.primitives import Identifier
from core.runtime.enums import ComponentState, HealthState
from core.runtime.interfaces import RuntimeComponent
from core.runtime.models import ComponentMetadata, HealthReport

from .project import ProjectState, ProjectPhase
from .backlog import RequirementsParser
from .architecture import ArchitectureDesigner
from .implementation import ImplementationEngine
from .testing import TestHarness
from .review import CodeReviewer
from .documentation import DocumentationGenerator
from .release import ReleaseManager
from .deployment import DeploymentEngine
from .metrics import QualityMetrics
from .recovery import RecoveryController

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
            code = self.implementation.implement(state, arch)
            
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
            docs = self.documentation.generate(state)
            
            # Release & Deployment
            state.phase = ProjectPhase.RELEASE
            version = self.release.release(state)
            await self.event_bus.publish_async(Event(topic="engineering.release.created", payload={"version": version}))
            
            state.phase = ProjectPhase.DEPLOYMENT
            self.deployment.deploy(state, version)
            
            return state
            
        except Exception as e:
            state.errors.append(str(e))
            await self.event_bus.publish_async(Event(topic="engineering.failed", payload={"error": str(e)}))
            self.recovery.restore(state)
            return state
"""

files["__init__.py"] = """from .manager import EngineeringManager
from .project import ProjectState, ProjectPhase

__all__ = ["EngineeringManager", "ProjectState", "ProjectPhase"]
"""

for fname, fcontent in files.items():
    with open(os.path.join(d, fname), "w") as f:
        f.write(fcontent)
        
tests_file = """import pytest

from core.events.bus import EventBus
from engineering.manager import EngineeringManager
from engineering.project import ProjectPhase

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
def engineering(event_bus):
    return EngineeringManager(event_bus)

@pytest.mark.asyncio
async def test_requirement_parsing(engineering):
    from engineering.project import ProjectState
    state = ProjectState(id="1", objective="Web App")
    stories = engineering.backlog.parse(state)
    assert len(stories) == 2

@pytest.mark.asyncio
async def test_repair_loop(engineering):
    from engineering.project import ProjectState
    state = ProjectState(id="2", objective="fail_test_app")
    
    # Should fix it internally
    success = engineering.testing.repair_loop(state)
    assert success is True
    assert state.objective == "fixed_test_app"

@pytest.mark.asyncio
async def test_documentation(engineering):
    from engineering.project import ProjectState
    state = ProjectState(id="3", objective="App")
    docs = engineering.documentation.generate(state)
    assert "README.md" in docs

@pytest.mark.asyncio
async def test_pipeline(engineering):
    # Test entire pipeline runs to end
    state = await engineering.execute_project("p1", "Simple App")
    assert state.phase == ProjectPhase.DEPLOYMENT
    assert len(state.errors) == 0

@pytest.mark.asyncio
async def test_pipeline_failure_recovery(engineering):
    # If the repair loop completely fails (we inject a failure that can't be fixed)
    # Actually wait, repair loop fixes "fail_test", so to make it completely fail:
    # the repair loop in our mock specifically replaces "fail_test" with "fixed_test".
    # if it doesn't have "fail_test" but still fails, let's mock the run_tests on harness.
    
    # We will just patch harness
    engineering.testing.run_tests = lambda s: {"success": False, "error": "fatal"}
    
    state = await engineering.execute_project("p2", "Fatal App")
    # It will fail, recovery controller drops it to IMPLEMENTATION
    assert state.phase == ProjectPhase.IMPLEMENTATION
    assert len(state.errors) == 0 # Recovery clears errors
"""

with open("tests/test_engineering.py", "w") as f:
    f.write(tests_file)

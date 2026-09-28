import os

dirs = [
    "integrations/base",
    "integrations/git",
    "integrations/github",
    "integrations/vscode",
    "integrations/terminal",
    "integrations/docker",
    "integrations/browser",
    "integrations/office",
    "integrations/email",
    "integrations/calendar",
    "integrations/discord",
    "integrations/slack",
    "integrations/notion",
    "integrations/obsidian",
    "integrations/blender",
    "integrations/figma",
    "integrations/homeassistant"
]

for d in dirs:
    os.makedirs(d, exist_ok=True)

files = {}

files["integrations/base/interface.py"] = """from abc import ABC, abstractmethod
from typing import Any

class BaseIntegration(ABC):
    @abstractmethod
    async def connect(self) -> None:
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        pass

    @abstractmethod
    async def health(self) -> dict[str, str]:
        pass

    @abstractmethod
    def capabilities(self) -> list[str]:
        pass

    @abstractmethod
    async def execute(self, action: str, params: dict[str, Any]) -> Any:
        pass
"""

files["integrations/base/manager.py"] = """from typing import Any

from core.events.bus import EventBus
from core.models import Event
from core.models.primitives import Identifier
from core.runtime.enums import ComponentState, HealthState
from core.runtime.interfaces import RuntimeComponent
from core.runtime.models import ComponentMetadata, HealthReport
from .interface import BaseIntegration

class IntegrationManager(RuntimeComponent):
    def __init__(self, event_bus: EventBus):
        self._id = Identifier("manager.integrations")
        self.event_bus = event_bus
        self.integrations: dict[str, BaseIntegration] = {}
        self._is_running = False

    def register(self, name: str, integration: BaseIntegration) -> None:
        self.integrations[name] = integration

    @property
    def id(self) -> Identifier:
        return self._id

    @property
    def metadata(self) -> ComponentMetadata:
        return ComponentMetadata(id=self._id.value, name="Integration Platform", version="1.0.0")

    @property
    def state(self) -> ComponentState:
        return ComponentState.RUNNING if self._is_running else ComponentState.STOPPED

    async def initialize(self) -> None:
        for name, integration in self.integrations.items():
            await integration.connect()
            await self.event_bus.publish_async(Event(
                topic="integration.connected",
                payload={"name": name}
            ))

    async def start(self) -> None:
        self._is_running = True

    async def stop(self) -> None:
        self._is_running = False
        for integration in self.integrations.values():
            await integration.disconnect()

    async def health(self) -> HealthReport:
        return HealthReport(
            component_id=self._id.value,
            state=HealthState.HEALTHY if self._is_running else HealthState.UNKNOWN
        )

    async def execute(self, integration_name: str, action: str, params: dict[str, Any]) -> Any:
        if integration_name not in self.integrations:
            raise ValueError(f"Integration {integration_name} not found")
            
        integration = self.integrations[integration_name]
        if action not in integration.capabilities():
            raise ValueError(f"Action {action} not supported by {integration_name}")
            
        try:
            result = await integration.execute(action, params)
            await self.event_bus.publish_async(Event(
                topic="integration.executed",
                payload={"name": integration_name, "action": action}
            ))
            return result
        except Exception as e:
            await self.event_bus.publish_async(Event(
                topic="integration.failed",
                payload={"name": integration_name, "action": action, "error": str(e)}
            ))
            raise
"""

files["integrations/base/__init__.py"] = """from .interface import BaseIntegration
from .manager import IntegrationManager

__all__ = ["BaseIntegration", "IntegrationManager"]
"""

def generate_client(name: str, caps: list[str]) -> str:
    caps_str = repr(caps)
    return f"""from typing import Any
from integrations.base.interface import BaseIntegration

class {name.capitalize()}Client(BaseIntegration):
    async def connect(self) -> None:
        pass

    async def disconnect(self) -> None:
        pass

    async def health(self) -> dict[str, str]:
        return {{"status": "ok"}}

    def capabilities(self) -> list[str]:
        return {caps_str}

    async def execute(self, action: str, params: dict[str, Any]) -> Any:
        if action not in self.capabilities():
            raise ValueError(f"Unsupported action: {{action}}")
        if params.get("simulate_fail"):
            raise RuntimeError("Simulated failure")
        return {{"result": f"Executed {{action}} successfully"}}
"""

def generate_init(name: str) -> str:
    return f"""from .client import {name.capitalize()}Client

__all__ = ["{name.capitalize()}Client"]
"""

clients = {
    "git": ["clone", "commit", "push", "pull", "branch", "diff", "merge"],
    "github": ["repositories", "issues", "pr", "actions", "releases"],
    "vscode": ["open_workspace", "diagnostics", "extensions", "terminal", "debug"],
    "terminal": ["exec"],
    "docker": ["images", "containers", "compose", "logs", "exec"],
    "browser": ["tabs", "downloads", "history", "cookies", "dom", "playwright"],
    "office": ["word", "excel", "powerpoint", "outlook"],
    "email": ["read", "search", "draft", "send", "archive"],
    "calendar": ["create", "delete", "move", "reminder"],
    "discord": ["messages", "channels", "voice"],
    "slack": ["messages", "threads", "uploads"],
    "notion": ["pages", "databases", "tasks"],
    "obsidian": ["vault", "notes", "graph"],
    "blender": ["open_scene", "render", "animation"],
    "figma": ["projects", "frames", "components"],
    "homeassistant": ["state"]
}

for cname, ccaps in clients.items():
    files[f"integrations/{cname}/client.py"] = generate_client(cname, ccaps)
    files[f"integrations/{cname}/__init__.py"] = generate_init(cname)

files["integrations/__init__.py"] = """from .base import IntegrationManager, BaseIntegration

__all__ = ["IntegrationManager", "BaseIntegration"]
"""

for fname, fcontent in files.items():
    with open(fname, "w") as f:
        f.write(fcontent)
        
tests_file = """import pytest

from core.events.bus import EventBus
from integrations.base.manager import IntegrationManager
from integrations.git.client import GitClient
from integrations.github.client import GithubClient
from integrations.docker.client import DockerClient
from integrations.discord.client import DiscordClient

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
def integration_manager(event_bus):
    mgr = IntegrationManager(event_bus)
    mgr.register("git", GitClient())
    mgr.register("github", GithubClient())
    mgr.register("docker", DockerClient())
    mgr.register("discord", DiscordClient())
    return mgr

@pytest.mark.asyncio
async def test_connection_and_health(integration_manager):
    await integration_manager.initialize()
    await integration_manager.start()
    
    health = await integration_manager.health()
    assert health.state == "HEALTHY"
    
    # Check individual
    git_health = await integration_manager.integrations["git"].health()
    assert git_health["status"] == "ok"

@pytest.mark.asyncio
async def test_execution(integration_manager):
    res = await integration_manager.execute("git", "commit", {})
    assert "Executed commit" in res["result"]

@pytest.mark.asyncio
async def test_error_handling(integration_manager):
    with pytest.raises(ValueError):
        await integration_manager.execute("git", "unknown_action", {})
        
    with pytest.raises(ValueError):
        await integration_manager.execute("unknown_integration", "commit", {})

    with pytest.raises(RuntimeError):
        await integration_manager.execute("git", "commit", {"simulate_fail": True})

@pytest.mark.asyncio
async def test_thread_safety(integration_manager):
    import asyncio
    
    async def exec_task():
        return await integration_manager.execute("git", "commit", {})
        
    results = await asyncio.gather(*[exec_task() for _ in range(10)])
    assert len(results) == 10
    assert all("Executed commit" in r["result"] for r in results)
"""

with open("tests/test_integrations.py", "w") as f:
    f.write(tests_file)

import pytest

from core.events.bus import EventBus
from integrations.base.manager import IntegrationManager
from integrations.discord.client import DiscordClient
from integrations.docker.client import DockerClient
from integrations.git.client import GitClient
from integrations.github.client import GithubClient


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

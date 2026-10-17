import asyncio
from abc import abstractmethod

from core.runtime.enums import HealthState
from core.runtime.models import HealthReport

from .interfaces import IAgent
from .models import AgentProfile, AgentResult, AgentTask, SharedContext


class BaseAgent(IAgent):
    """Abstract base implementation for specific agents."""

    def __init__(self, profile: AgentProfile) -> None:
        self._profile = profile
        self._is_healthy = True

    @property
    def profile(self) -> AgentProfile:
        return self._profile

    @abstractmethod
    async def execute(self, task: AgentTask, context: SharedContext) -> AgentResult:
        # To be implemented by subclasses
        pass

    async def health(self) -> HealthReport:
        return HealthReport(
            component_id=f"agent.{self._profile.id.value}",
            state=HealthState.HEALTHY if self._is_healthy else HealthState.UNHEALTHY
        )

    async def _simulate_work(self, delay: float = 0.1) -> None:
        """Helper for mocked cognitive latency."""
        await asyncio.sleep(delay)

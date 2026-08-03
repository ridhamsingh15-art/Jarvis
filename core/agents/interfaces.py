import builtins
from abc import ABC, abstractmethod
from typing import Any

from core.models.primitives import Identifier
from core.runtime.models import HealthReport

from .enums import ConsensusStrategy
from .models import AgentProfile, AgentResult, AgentTask, SharedContext, Vote


class IAgent(ABC):
    """Base interface for all agents in the framework."""

    @property
    @abstractmethod
    def profile(self) -> AgentProfile:
        pass

    @abstractmethod
    async def execute(self, task: AgentTask, context: SharedContext) -> AgentResult:
        pass

    @abstractmethod
    async def health(self) -> HealthReport:
        pass


class ICoordinator(ABC):
    """Interface for the master coordinator."""

    @abstractmethod
    async def assign(self, intent: str, payload: dict[str, Any]) -> AgentResult:
        pass


class IAgentRegistry(ABC):
    """Interface for managing available agents."""

    @abstractmethod
    def register(self, agent: IAgent) -> None:
        pass
        
    @abstractmethod
    def get_agent(self, agent_id: Identifier) -> IAgent | None:
        pass

    @abstractmethod
    def get_agents_by_capability(self, capability_name: str) -> builtins.list[IAgent]:
        pass


class IVotingMechanism(ABC):
    """Interface for evaluating consensus algorithms."""

    @abstractmethod
    def evaluate(self, votes: builtins.list[Vote], strategy: ConsensusStrategy) -> Vote | None:
        pass


class ISharedMemory(ABC):
    """Interface for thread-safe context state sharing across parallel agents."""

    @abstractmethod
    def write(self, key: str, value: Any) -> None:
        pass

    @abstractmethod
    def read(self, key: str) -> Any | None:
        pass

    @abstractmethod
    def snapshot(self, session_id: Identifier) -> SharedContext:
        pass

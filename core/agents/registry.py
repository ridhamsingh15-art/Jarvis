import builtins
import threading

from core.models.primitives import Identifier

from .exceptions import RegistryError
from .interfaces import IAgent, IAgentRegistry


class DefaultAgentRegistry(IAgentRegistry):
    """Thread-safe dynamic agent tracker."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._agents: dict[str, IAgent] = {}

    def register(self, agent: IAgent) -> None:
        if not agent or not agent.profile:
            raise RegistryError("Cannot register invalid agent.")
            
        with self._lock:
            self._agents[agent.profile.id.value] = agent

    def get_agent(self, agent_id: Identifier) -> IAgent | None:
        with self._lock:
            return self._agents.get(agent_id.value)

    def get_agents_by_capability(self, capability_name: str) -> builtins.list[IAgent]:
        with self._lock:
            results: builtins.list[IAgent] = []
            for agent in self._agents.values():
                for cap in agent.profile.capabilities:
                    if cap.name == capability_name:
                        results.append(agent)
                        break
            return results

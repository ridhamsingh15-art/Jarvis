from abc import ABC, abstractmethod
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

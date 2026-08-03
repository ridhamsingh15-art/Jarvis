from typing import Any

from integrations.base.interface import BaseIntegration


class CalendarClient(BaseIntegration):
    async def connect(self) -> None:
        pass

    async def disconnect(self) -> None:
        pass

    async def health(self) -> dict[str, str]:
        return {"status": "ok"}

    def capabilities(self) -> list[str]:
        return ['create', 'delete', 'move', 'reminder']

    async def execute(self, action: str, params: dict[str, Any]) -> Any:
        if action not in self.capabilities():
            raise ValueError(f"Unsupported action: {action}")
        if params.get("simulate_fail"):
            raise RuntimeError("Simulated failure")
        return {"result": f"Executed {action} successfully"}

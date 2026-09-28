"""
Stub integration client base.

All external integrations that are not yet implemented inherit from
this class. It provides the BaseIntegration contract with deterministic
stub behaviour so the integration platform can be exercised in tests
without real connections.
"""
from __future__ import annotations

from typing import Any

from .interface import BaseIntegration


class StubIntegrationClient(BaseIntegration):
    """Parametrized stub that satisfies BaseIntegration for unimplemented integrations."""

    def __init__(self, name: str, caps: list[str]) -> None:
        self._name = name
        self._caps = caps

    async def connect(self) -> None:
        pass

    async def disconnect(self) -> None:
        pass

    async def health(self) -> dict[str, str]:
        return {"status": "ok"}

    def capabilities(self) -> list[str]:
        return self._caps

    async def execute(self, action: str, params: dict[str, Any]) -> Any:
        if action not in self._caps:
            raise ValueError(f"Unsupported action: {action}")
        if params.get("simulate_fail"):
            raise RuntimeError("Simulated failure")
        return {"result": f"Executed {action} successfully"}

from typing import Any

from .interfaces import IReasoner
from .models import Inference
from .world_model import WorldModel


class LogicalReasoner(IReasoner):
    def __init__(self, world: WorldModel):
        self.world = world

    def reason(self, context: dict[str, Any]) -> list[Inference]:
        # Mock deductive inference
        state = self.world.get_state()
        if "rain" in state and state["rain"] == "OBJECT":
            return [Inference("Ground is wet", 1.0, ["rain exists"])]
        return []

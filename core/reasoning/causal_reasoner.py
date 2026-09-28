from typing import Any

from .interfaces import IReasoner
from .models import Inference
from .world_model import WorldModel


class CausalReasoner(IReasoner):
    def __init__(self, world: WorldModel):
        self.world = world

    def reason(self, context: dict[str, Any]) -> list[Inference]:
        # Mock causal inference
        if "action" in context:
            return [Inference("Outcome A", 0.8, ["action triggered"])]
        return []

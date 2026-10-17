from typing import Any

from .interfaces import IReasoner
from .models import Inference
from .world_model import WorldModel


class ProbabilisticReasoner(IReasoner):
    def __init__(self, world: WorldModel):
        self.world = world

    def reason(self, context: dict[str, Any]) -> list[Inference]:
        # Mock risk assessment
        risk_level = context.get("risk", 0.5)
        return [Inference("Risk Assessment", 1.0 - risk_level, ["historical data"])]

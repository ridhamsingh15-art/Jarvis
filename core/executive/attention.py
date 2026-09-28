from dataclasses import dataclass


@dataclass
class AttentionState:
    focus: str
    importance: float
    urgency: float
    novelty: float
    risk: float
    confidence: float

class AttentionSystem:
    def __init__(self) -> None:
        self.state = AttentionState(
            focus="idle",
            importance=0.0,
            urgency=0.0,
            novelty=0.0,
            risk=0.0,
            confidence=1.0
        )

    def update(self, **kwargs: float | str) -> None:
        for k, v in kwargs.items():
            if hasattr(self.state, k):
                setattr(self.state, k, v)

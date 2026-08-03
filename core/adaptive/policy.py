from dataclasses import dataclass


@dataclass(frozen=True)
class LearningPolicy:
    """
    Configuration and thresholds for the adaptive learning subsystem.
    """
    minimum_repetitions: int = 3
    minimum_confidence: float = 0.7
    minimum_success_rate: float = 0.8
    minimum_executions: int = 5

from typing import Protocol, runtime_checkable


@runtime_checkable
class BackoffPolicy(Protocol):
    def next_delay(self, attempt: int) -> float:
        """Returns the delay in seconds for the given retry attempt."""
        ...

class FixedBackoff(BackoffPolicy):
    def __init__(self, delay_seconds: float):
        self.delay = delay_seconds
        
    def next_delay(self, attempt: int) -> float:
        return self.delay

class LinearBackoff(BackoffPolicy):
    def __init__(self, base_delay: float):
        self.base = base_delay
        
    def next_delay(self, attempt: int) -> float:
        return self.base * attempt

class ExponentialBackoff(BackoffPolicy):
    def __init__(self, base_delay: float, factor: float = 2.0, max_delay: float = 3600.0):
        self.base = base_delay
        self.factor = factor
        self.max_delay = max_delay
        
    def next_delay(self, attempt: int) -> float:
        delay = self.base * (self.factor ** (attempt - 1))
        return min(delay, self.max_delay)

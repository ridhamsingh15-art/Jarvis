from abc import ABC, abstractmethod
from typing import Any


class Trigger(ABC):
    @abstractmethod
    def next_fire_time(self, current_time: float) -> float | None:
        """Returns the absolute timestamp for the next firing, or None if done."""
        
    @abstractmethod
    def serialize(self) -> tuple[str, dict[str, Any]]:
        pass

class ImmediateTrigger(Trigger):
    def __init__(self):
        self._fired = False
        
    def next_fire_time(self, current_time: float) -> float | None:
        if self._fired:
            return None
        self._fired = True
        return current_time # Fire right now

    def serialize(self) -> tuple[str, dict[str, Any]]:
        return "IMMEDIATE", {}

class DelayedTrigger(Trigger):
    def __init__(self, delay_seconds: float):
        self.delay = delay_seconds
        self._fired = False
        
    def next_fire_time(self, current_time: float) -> float | None:
        if self._fired:
            return None
        self._fired = True
        return current_time + self.delay

    def serialize(self) -> tuple[str, dict[str, Any]]:
        return "DELAYED", {"delay_seconds": self.delay}

class IntervalTrigger(Trigger):
    """Fires every interval_seconds. Optionally capped by max_fires."""
    def __init__(self, interval_seconds: float, max_fires: int = -1):
        self.interval = interval_seconds
        self.max_fires = max_fires
        self._fire_count = 0
        self._start_time: float | None = None
        
    def next_fire_time(self, current_time: float) -> float | None:
        if self.max_fires > 0 and self._fire_count >= self.max_fires:
            return None
            
        if self._start_time is None:
            self._start_time = current_time
            
        self._fire_count += 1
        return self._start_time + (self.interval * self._fire_count)

    def serialize(self) -> tuple[str, dict[str, Any]]:
        return "INTERVAL", {"interval_seconds": self.interval, "max_fires": self.max_fires}

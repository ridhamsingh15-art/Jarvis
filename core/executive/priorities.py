import queue
from dataclasses import dataclass, field
from typing import Any


@dataclass(order=True)
class PriorityTask:
    priority: int
    task_id: str = field(compare=False)
    payload: dict[str, Any] = field(default_factory=dict, compare=False)

class PriorityManager:
    def __init__(self) -> None:
        self.q: queue.PriorityQueue = queue.PriorityQueue()

    def add_task(self, task_id: str, priority: int, payload: dict[str, Any] | None = None) -> None:
        self.q.put(PriorityTask(priority=priority, task_id=task_id, payload=payload or {}))

    def get_next(self) -> PriorityTask | None:
        if not self.q.empty():
            return self.q.get()
        return None
